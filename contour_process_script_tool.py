import arcpy
import os
##import multiprocessing
import itertools
import time
import list_datasets

#TODO: make class for creating directories if they dont exist 
#uses fishnet to process large contour dataset
#get parameter inputs
workspace = arcpy.GetParameterAsText(0)
main_raster = arcpy.GetParameterAsText(1)
buffer_dist = float(arcpy.GetParameterAsText(2))
smoothing_method = arcpy.GetParameterAsText(3)
tolerance = arcpy.GetParameterAsText(4)
number_columns = arcpy.GetParameterAsText(5)
number_rows = arcpy.GetParameterAsText(6)
#display inputs
arcpy.AddMessage('Workspace geodatabase: {0}'.format(workspace))
arcpy.AddMessage('Input DEM: {0}'.format(main_raster))
arcpy.AddMessage('Processing Buffer: {0}'.format(buffer_dist))
arcpy.AddMessage('Smoothing Method: {0}'.format(smoothing_method))
arcpy.AddMessage('Smoothing Tolerance: {0}'.format(tolerance))
arcpy.AddMessage('Fishnet Columns: {0}'.format(number_columns))
arcpy.AddMessage('Fishnet Rows: {0}'.format(number_rows))



###stand-alone script variables
##workspace = 'c:/Kent_Contour/test/workspace/test.gdb'
##main_raster = 'c:/Kent_Contour/test/raw_DEM/DEM.img'
###set buffer distance for tiles
##buffer_dist = 225
###smooth line tolerance--this number is in the same units as the geometry of the feature being smoothed. If
### 'BEZIER_INTERPOLATION' is selected as smoothing method, set this to '0'
##tolerance = 15
###set smoothing method: 'PAEK' or 'BEZIER_INTERPOLATION' 
##smoothing_method = 'PAEK'
##
###TODO:Implement console raw input for number of columns/rows (use updateParams code from script tool validation code)
##number_columns = '6'
##number_rows = '1'

#get DEM spatial ref and dimensions
dem = arcpy.sa.Raster(main_raster)
spatial_ref = dem.extent.spatialReference.factoryCode
##raster_height = int(dem.height.real)
##raster_width = int(dem.width.real)


#output directories and datasets
dem_filled_out = os.path.join(os.path.dirname(workspace),'dem_filled')
contours_fill_out = os.path.join(workspace,'Contours_fill')
contours_raw_out = os.path.join(workspace,'Contours_raw')
contours_smooth_out = os.path.join(workspace,'Contours_smooth')
contours_final_out = os.path.join(workspace,'Contours_final_clip')
#set topology dataset and error output location
topo_output = contours_final_out
error_output = os.path.join(workspace,'Topology_Errors')

# set topology rule
rule = 'Must Not Intersect (Line)'

#fishnet variables
fishnet_out = os.path.join(os.path.dirname(workspace),'fishnet.shp')
origin_coord = '{0} {1}'.format(dem.extent.lowerLeft.X,dem.extent.lowerLeft.Y)
y_coord = '{0} {1}'.format(dem.extent.lowerLeft.X,dem.extent.upperLeft.Y)
cell_width = '0'
cell_height = '0'
##number_rows = ''
##number_columns = ''
opposite_corner_coord = '{0} {1}'.format(dem.extent.upperRight.X,dem.extent.upperRight.Y)
labels = 'NO_LABELS'
#extent is set by origin and opposite corner coords -- no need to use template 
template = '#'
geometry_type = 'POLYGON'



def create_fishnet(number_columns,number_rows):
	'''(str,str) -> output shapefile "fishnet.shp"
	Inputs: number_columns (str) = Takes any integer as a string
	number_rows (str) = Takes any integer as a string
	Creates 'fishnet' shapefile in the directory where the workspace is located.
	Adds 'Name' field populated with the value 'Tile_#', where # = the OID of each fishnet polygon.
	Returns the full file path.
	'''
	arcpy.CreateFishnet_management(fishnet_out,origin_coord,y_coord,cell_width,
								   cell_height,number_rows,number_columns,opposite_corner_coord,
								   labels,template,geometry_type)
	arcpy.AddField_management(fishnet_out,'Name','TEXT')
	with arcpy.da.UpdateCursor(fishnet_out,['OID@','Name']) as cursor:
		for oid,name in cursor:
			row = (oid,'Tile_{0:02d}'.format(oid))
			cursor.updateRow(row)
	return fishnet_out

			

def get_final_tiles(fishnet_out):
	'''(full path to fishnet shapefile)-> dict
	Input: Fishnet feature class.
	Iterates over each feature in the the feature class, creating temporary 
	polygon objects with extents equal to each feature extent. These will be used as final
	processing extents for clipping the buffered tiles. 
	Output: Dict with tile names as keys and polygon objects as values.
	'''
	with arcpy.da.SearchCursor(fishnet_out,['Name','SHAPE@']) as rows:
		tile_dict = {}
		array = arcpy.Array()
		for row in rows:
			name = row[0]
			extent = row[1].extent
			array.add(extent.lowerLeft)
			array.add(extent.lowerRight)
			array.add(extent.upperRight)
			array.add(extent.upperLeft)
			tile_dict[name] = arcpy.Polygon(array)
			array.removeAll()
			del row
		del array
	return tile_dict
	
def get_buffered_tiles(fishnet_out,buffer_dist):
	''' (full path to fishnet shapefile,int) -> dict
	Input: Takes full path string to fishnet shapefile and an integer value 
	representing the buffer distance. This value is a linear unit. 
	Identical to get_final_tiles, but with a buffer. These temporary polygon objects
	will be used for processing.
	Output: Returns a dict with tile names as keys and buffered polygon objects as values.	
	'''
	with arcpy.da.SearchCursor(fishnet_out,['Name','SHAPE@']) as rows:
		tiles_buff = {}
		array = arcpy.Array()
		for row in rows:
			name = row[0]
			extent = row[1].extent
			array.add(extent.lowerLeft)
			array.add(extent.lowerRight)
			array.add(extent.upperRight)
			array.add(extent.upperLeft)
			tiles_buff[name] = arcpy.Polygon(array).buffer(buffer_dist)
			array.removeAll()
			del row
		del array
	return tiles_buff
		
	
def fill_DEM(inras,name,tile,output_dir):
	'''(raster,string,polygon object,path string) -> output path string
	Input: Takes a raster dataset and polygon object.
	Sets processing extent to the polygon extent. 
	Executes Fill geoprocess on the raster dataset.
	Saves output.
	Output: Returns output path string. 
	'''
	arcpy.env.extent = tile.extent
	output = os.path.join(output_dir,name)
	outFill = arcpy.sa.Fill(inras)
	outFill.save(output)
	return output
	

def create_contours(inras,name,tile,output_dir):
	''' (raster,string,polygon object,path string)->output path string
	Sets processing extent to polygon object extent.
	Executes Contour geoprocess on raster dataset.
	Saves output according to name and output_dir parameters. 
	Returns output path string.
	'''
	arcpy.env.extent = tile.extent
	output = os.path.join(output_dir,name)
	arcpy.sa.Contour(inras,output,2,0)
	return output

def create_filled_contours(inras,output_dir):
	''' (raster,path string) -> output path string
	Executes Contour geoprocess on raster dataset. 
	Outputs shapefile with prefix "Fill" according to the name of the input raster and output_dir parameter.
	Returns output path string.	
	'''
##    arcpy.env.extent = arcpy.sa.Raster(inras).extent
	name = 'Fill_{0}'.format(os.path.splitext(os.path.basename(inras))[0])
	output = os.path.join(output_dir,name)
	arcpy.sa.Contour(inras,output,2,0)
	return output
	

def att_contours(fc,filled):
	''' (feature class, feature class) -> None 
	Updates attribute table and deletes features less than 100 in length.
	Attributes each feature with contour type: Intermediate,Index,Depression. 
	Gets depression contour type by selecting all contours which do not intersect the
	filled contours. These are the depression contours.
	Returns none.	
	'''
##    arcpy.env.extent = arcpy.Describe(fc).extent
	expression = 'getType(!Contour!,!Type!)'
	codeblock = """def getType(con,typ):
		if con % 10 == 0 and typ == 'Depression':
			return 'Index_Depression'      
		elif con % 10 == 0 and typ != 'Depression':
			return 'Index'
		elif con % 10 != 0 and typ == 'Depression':
			return 'Intermediate_Depression'
		else:
			return 'Intermediate'"""
	arcpy.MakeFeatureLayer_management(fc,'contour_lyr')
##    arcpy.CalculateField_management('contour_lyr','Length','!shape.length@feet!','PYTHON')
	arcpy.SelectLayerByAttribute_management('contour_lyr','NEW_SELECTION','Shape_Length < 100')
	arcpy.DeleteFeatures_management('contour_lyr')
	arcpy.SelectLayerByAttribute_management('contour_lyr','CLEAR_SELECTION')
	arcpy.SelectLayerByLocation_management('contour_lyr','INTERSECT',filled,'','NEW_SELECTION')
	arcpy.SelectLayerByAttribute_management('contour_lyr','SWITCH_SELECTION')
	arcpy.CalculateField_management('contour_lyr','Type','"Depression"','PYTHON_9.3')
	arcpy.SelectLayerByAttribute_management('contour_lyr','CLEAR_SELECTION')
	arcpy.CalculateField_management('contour_lyr','Type',expression,'PYTHON_9.3',codeblock)
	return None 

 

def smooth_lines(fc,output_dir):
	'''(feature class,path string)-> output path string
	Takes a feature class and output path string as inputs.
	Executes Smoothline geoprocess on feature class.
	Saves output prefixed with "Smooth" to output_dir.
	Returns output path string.
	'''
##    arcpy.env.extent = dem.extent
	name = 'Smooth_{0}'.format(os.path.basename(fc))
	output = os.path.join(output_dir,name)
	arcpy.cartography.SmoothLine(fc,output,smoothing_method,tolerance)
	return output

# currently not working as intended. does not trim line segments at all. 
def trim_dangles(fc):
	with arcpy.da.Editor(workspace) as edit: 
	##    arcpy.env.extent = arcpy.Describe(fc).extent
		arcpy.TrimLine_edit(fc,'10 Feet','DELETE_SHORT')
		


def clip_fcs(fc,clip_fc,name,output_dir):
	''' (feature class,clip feature,str,directory path string) -> output path string
	Executes Clip geoprocess on input feature class, using clip_fc as clip feature.
	Saves output with "Final" prefix to output_dir.
	Returns output path string.
	'''
##    arcpy.env.extent = arcpy.Describe(fc).extent
	fc_name = 'Final_{0}'.format(name)
	output = os.path.join(output_dir,fc_name)
	arcpy.Clip_analysis(fc,clip_fc,output)
	return output



def create_topology(fc,topo_output,rule,error_output):
	'''(feature class,topology output location,topology rule,topology error output location)-> error output location
	Creates a topology in topo_output. Adds fc to newly created topology.
	Adds rule to topology. Validates topology. Exports topology errors to error_output.
	Returns error_output string.	
	'''
	toponame = '{0}_topo'.format(os.path.basename(fc))
	topo_path = os.path.join(topo_output,toponame)
	arcpy.CreateTopology_management(topo_output,toponame)
	arcpy.AddFeatureClassToTopology_management(topo_path, fc, 1)
	arcpy.AddRuleToTopology_management(topo_path,rule,fc)
	arcpy.ValidateTopology_management(topo_path)
	arcpy.ExportTopologyErrors_management(topo_path,error_output,'{0}_errors'.format(os.path.basename(fc)))
	return error_output
	
  
def get_total_errors(point_errors,line_errors,error_output):
	'''(list of feature classes,list of feature classes,topology error location)-> None
	Merges all point error features into a single feature class. Repeats for line errors.
	Counts total number of errors for each feature class.
	Appends the total to the name of each feature class. 
	Returns tuple of (total point errors, total line errors)
	'''
	total_line_errors = os.path.join(error_output,'All_Line_Errors')
	total_point_errors = os.path.join(error_output,'All_Point_Errors')
	arcpy.Merge_management(point_errors,total_point_errors)
	arcpy.Merge_management(line_errors,total_line_errors)
	point_count = arcpy.GetCount_management(total_point_errors)
	line_count = arcpy.GetCount_management(total_line_errors)
	arcpy.Rename_management(total_line_errors,'{0}_{1}'.format(total_line_errors,line_count))
	arcpy.Rename_management(total_point_errors,'{0}_{1}'.format(total_point_errors,point_count))
	return (point_count,line_count)
	

def main():
	#set workspace
##    arcpy.env.workspace = os.path.split(workspace)[0]
	#set output coord. system
	arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(spatial_ref)
	#set overwrite status
	arcpy.env.overwriteOutput = True
	#check out spatial analyst extension
	arcpy.CheckOutExtension("Spatial")
	
	#make all needed directories and datasets
	arcpy.AddMessage('Creating directories...')
	if not arcpy.Exists(dem_filled_out):
		os.mkdir(dem_filled_out)
##    os.mkdir('{0}/dem_tiles'.format(os.path.split(workspace)[0]))
##    os.mkdir('{0}/dem_tiles_buff'.format(os.path.split(workspace)[0]))
	if not arcpy.Exists(contours_raw_out):
		arcpy.CreateFeatureDataset_management(workspace,'Contours_raw',main_raster)
	if not arcpy.Exists(contours_fill_out):
		arcpy.CreateFeatureDataset_management(workspace,'Contours_fill',main_raster)
	if not arcpy.Exists(contours_smooth_out):
		arcpy.CreateFeatureDataset_management(workspace,'Contours_smooth',main_raster)
	if not arcpy.Exists(contours_final_out):
		arcpy.CreateFeatureDataset_management(workspace,'Contours_final_clip',main_raster)
	if not arcpy.Exists(error_output):
		arcpy.CreateFeatureDataset_management(workspace,'Topology_Errors',main_raster)
		
	#create fishnet tiles and get list of all tiles
	#get fishnet columns and rows
	if not arcpy.Exists(fishnet_out):
		arcpy.AddMessage('Creating fishnet...')
		create_fishnet(number_columns,number_rows)

	# initialize feature class lists
	tiles_fill = []
	contour_fcs = []
	contour_fill = []
	contour_smooth = []
	contour_final = []
	point_errors = []
	line_errors = []
  
	#execute fill
	arcpy.AddMessage('Creating filled DEM tiles...')
	tiles_buff = get_buffered_tiles(fishnet_out,buffer_dist)
	for name,tile in tiles_buff.iteritems():
		tiles_fill.append(fill_DEM(main_raster,name,tile,dem_filled_out))
	tiles_fill.sort()
	
	
	#execute contour creation
	arcpy.AddMessage('Creating contour features...' )  
	for name,tile in tiles_buff.iteritems(): 
		contour_fcs.append(create_contours(main_raster,name,tile,contours_raw_out))
	contour_fcs.sort()
	time.sleep(1)
	for fc in contour_fcs:
		arcpy.AddField_management(fc,'Type','TEXT')

	#reset processing extent to full dataset
	arcpy.env.extent = dem.extent
	
	#execute filled contour creation
	arcpy.AddMessage('Creating filled contour features...')
	for inras in tiles_fill:
		contour_fill.append(create_filled_contours(inras,contours_fill_out))
	contour_fill.sort()
	

	#execute attribute update
	arcpy.AddMessage('Deleting short contours and updating attribute table with index, intermediate and depression values...')
	for fc,fill in itertools.izip(contour_fcs,contour_fill):
		att_contours(fc,fill)


	#execute smooth lines
	arcpy.AddMessage('Smoothing contours...')
	for fc in contour_fcs:
		contour_smooth.append(smooth_lines(fc,contours_smooth_out))
	contour_smooth.sort()

	
	#create dictionary joining tile names to features, and execute final clip
	contour_dict = {i:k for i,k in itertools.izip(sorted(get_final_tiles(fishnet_out)),contour_smooth)}
	clip_tiles_dict = get_final_tiles(fishnet_out)
	arcpy.AddMessage('Executing final clip to remove edge effects...')
	for name in contour_dict:
		fc = contour_dict[name]
		clip_fc = clip_tiles_dict[name]
		contour_final.append(clip_fcs(fc,clip_fc,name,contours_final_out))

##    #execute trim dangles 
##    #TODO: Trim line encountered error "Invalid Topology". Possibly memory issue, or need to run "Check/Repair Geometry"
##    print 'Executing trim line to remove dangles...'
##    for fc in contour_final:
##        trim_dangles(fc)

	#run topology and export errors
	arcpy.AddMessage('Creating topology and validating...')
	for fc in contour_final:
		create_topology(fc,topo_output,rule,error_output)

	#merge errors, and get total error count
	arcpy.AddMessage('Merging point errors and getting total count...')
	point_errors = list_datasets.list_datasets(error_output,datatype='FeatureClass',type='Point')
	line_errors = list_datasets.list_datasets(error_output,datatype='FeatureClass',type='Polyline')
	point_total,line_total = get_total_errors(point_errors,line_errors,error_output)
	arcpy.AddMessage('Total topology errors: {0} point errors, {1} line errors'.format(point_total,line_total))

	arcpy.AddMessage('Final contour datasets successfully created.')
	

	
if __name__ == '__main__':
	start_time = time.clock()
	main()
	end_time = time.clock()
	arcpy.AddMessage('Main process is complete. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60))
##    end_time = time.clock()
##    print 'Main process encountered an error. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60)


			
		
		
	
