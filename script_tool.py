import arcpy
import os
##import multiprocessing
import itertools
import time

#get parameter inputs
workspace = arcpy.GetParameterAsText(0)
main_raster = arcpy.GetParameterAsText(1)
buffer_dist = float(arcpy.GetParameterAsText(2))
smoothing_method = arcpy.GetParameterAsText(3)
tolerance = arcpy.GetParameterAsText(4)
number_columns = arcpy.GetParameterAsText(5)
number_rows = arcpy.GetParameterAsText(6)



###stand-alone script variables
##workspace = 'c:/Kent_Contour/test/workspace/test.gdb'
##main_raster = 'c:/Kent_Contour/test/raw_DEM/DEM.img'
###set buffer distance for tiles
##buffer_dist = 300
###smooth line tolerance--this number is in the same units as the geometry of the feature being smoothed. If
### 'BEZIER_INTERPOLATION' is selected as smoothing method, set this to '0'
##tolerance = 15
###set smoothing method: 'PAEK' or 'BEZIER_INTERPOLATION' 
##smoothing_method = 'PAEK'


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





#to get number of tiles (based on raster grid row/column count)
##def counter(n):
##    for i in range(1,n):
##        yield i
##
##def get_factors(n):
##    factors = [i for i in counter(n) if n % i == 0]
####    print 'The raster grid height/width can be evenly divided by these factors: {0}'.format(factors)
####    result = int(max([f for f in factors if f in range(1,50)]))
##    return factors



def create_fishnet(number_columns,number_rows):
    arcpy.CreateFishnet_management(fishnet_out,origin_coord,y_coord,cell_width,
                                   cell_height,number_rows,number_columns,opposite_corner_coord,
                                   labels,template,geometry_type)
    arcpy.AddField_management(fishnet_out,'Name','TEXT')
    with arcpy.da.UpdateCursor(fishnet_out,['OID@','Name']) as cursor:
        for oid,name in cursor:
            row = (oid,'Tile_{0:02d}'.format(oid))
            cursor.updateRow(row)

            
def get_tile_names():
    with arcpy.da.SearchCursor(fishnet_out,'Name') as rows:
        name_list = []
        for row in rows:
            name_list.append(row[0])
            del row
        name_list.sort()
    return name_list


def get_tiles():
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
    
def get_buffered_tiles():
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
        
    
def fill_DEM(inras,name,tile):
    arcpy.env.extent = tile.extent
    outFill = arcpy.sa.Fill(inras)
    outFill.save(os.path.join(dem_filled_out,name))
    

def create_contours(inras,name,tile):
    arcpy.env.extent = tile.extent
    output = os.path.join(contours_raw_out,name)
    arcpy.sa.Contour(inras,output,2,0)

def create_filled_contours(inras):
##    arcpy.env.extent = arcpy.sa.Raster(inras).extent
    name = 'Fill_{0}'.format(os.path.splitext(os.path.basename(inras))[0])
    output = os.path.join(contours_fill_out,name)
    arcpy.sa.Contour(inras,output,2,0)
    

def att_contours(fc,filled):
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

 

def smooth_lines(fc):
##    arcpy.env.extent = dem.extent
    name = 'Smooth_{0}'.format(os.path.basename(fc))
    output = os.path.join(contours_smooth_out,name)
    arcpy.cartography.SmoothLine(fc,output,smoothing_method,tolerance)

def trim_dangles(fc):
    with arcpy.da.Editor(workspace) as edit: 
    ##    arcpy.env.extent = arcpy.Describe(fc).extent
        arcpy.TrimLine_edit(fc,'10 Feet','DELETE_SHORT')
        


def clip_fcs(name,fc):
##    arcpy.env.extent = arcpy.Describe(fc).extent
    clip_tiles_dict = get_tiles()
    fc_name = 'Final_{0}'.format(name)
    tile = clip_tiles_dict[name] 
    output = os.path.join(contours_final_out,fc_name)
    arcpy.Clip_analysis(fc,tile,output)



def create_topology(fc):
    toponame = '{0}_topo'.format(os.path.basename(fc))
    topo_path = os.path.join(topo_output,toponame)
    arcpy.CreateTopology_management(topo_output,toponame)
    arcpy.AddFeatureClassToTopology_management(topo_path, fc, 1)
    arcpy.AddRuleToTopology_management(topo_path,rule,fc)
    arcpy.ValidateTopology_management(topo_path)
    arcpy.ExportTopologyErrors_management(topo_path,error_output,'{0}_errors'.format(os.path.basename(fc)))
    
  
def get_total_errors(point_errors,line_errors):
    total_line_errors = os.path.join(error_output,'All_Line_Errors')
    total_point_errors = os.path.join(error_output,'All_Point_Errors')
    arcpy.Merge_management(point_errors,total_point_errors)
    arcpy.Merge_management(line_errors,total_line_errors)
    point_count = arcpy.GetCount_management(total_point_errors)
    line_count = arcpy.GetCount_management(total_line_errors)
    arcpy.Rename_management(total_line_errors,'{0}_{1}'.format(total_line_errors,line_count))
    arcpy.Rename_management(total_point_errors,'{0}_{1}'.format(total_point_errors,point_count))
    

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
    arcpy.AddMessage('Executing fill on DEM...')
    tiles_buff = get_buffered_tiles()
    for name,tile in tiles_buff.iteritems():
        fill_DEM(main_raster,name,tile)
    for dirpath,dirname,filenames in arcpy.da.Walk(dem_filled_out):
        for fn in filenames:
            tiles_fill.append(os.path.join(dirpath,fn))
    tiles_fill.sort()
                          
    
    #execute contour creation
    arcpy.AddMessage('Creating contour shapefiles...' )  
    for name,tile in tiles_buff.iteritems(): 
        create_contours(main_raster,name,tile)
    for dirpath,dirname,filenames in arcpy.da.Walk(contours_raw_out):
        for fn in filenames:
            contour_fcs.append(os.path.join(dirpath,fn))
    contour_fcs.sort()
    time.sleep(1)
    for fc in contour_fcs:
        arcpy.AddField_management(fc,'Type','TEXT')

    #reset processing extent to full dataset
    arcpy.env.extent = dem.extent
    #execute filled contour creation
    arcpy.AddMessage('Creating filled contour shapefiles...')
    for inras in tiles_fill:
        create_filled_contours(inras)
    for dirpath,dirname,filenames in arcpy.da.Walk(contours_fill_out):
        for fn in filenames:
            contour_fill.append(os.path.join(dirpath,fn))
    contour_fill.sort()

    #execute attribute update
    arcpy.AddMessage('Deleting short contours and updating attribute table with index, intermediate and depression values...')
    for fc,fill in itertools.izip(contour_fcs,contour_fill):
        att_contours(fc,fill)


    #execute smooth lines
    arcpy.AddMessage('Smoothing contours...')
    for fc in contour_fcs:
        smooth_lines(fc)
    for dirpath,dirname,filenames in arcpy.da.Walk(contours_smooth_out):
        for fn in filenames:
            contour_smooth.append(os.path.join(dirpath,fn))
    contour_smooth.sort()



    #create dictionary joining tile names to features, and execute final clip
    tile_names = get_tile_names()
    contour_dict = dict(itertools.izip(tile_names,contour_smooth))
    arcpy.AddMessage('Executing final clip to remove edge effects...')
    for name,fc in contour_dict.iteritems():
        clip_fcs(name,fc)
    for dirpath,dirname,filenames in arcpy.da.Walk(contours_final_out):
        for fn in filenames:
            contour_final.append(os.path.join(dirpath,fn))


##    #execute trim dangles 
##    #TODO: Trim line encountered error "Invalid Topology". Possibly memory issue, or need to run "Check/Repair Geometry"
##    print 'Executing trim line to remove dangles...'
##    for fc in contour_final:
##        trim_dangles(fc)

    #run topology and export errors
    arcpy.AddMessage('Creating topology and validating...')
    map(create_topology,contour_final)

    #merge errors, and get total error count
    arcpy.AddMessage('Merging point errors and getting total count...')
    for dirpath,dirname,filenames in arcpy.da.Walk(error_output,datatype='FeatureClass',type='Point'):
        for fn in filenames:
            point_errors.append(os.path.join(dirpath,fn))
    for dirpath,dirname,filenames in arcpy.da.Walk(error_output,datatype='FeatureClass',type='Polyline'):
        for fn in filenames:
            line_errors.append(os.path.join(dirpath,fn))
    get_total_errors(point_errors,line_errors)

    



    arcpy.AddMessage('Final contour datasets successfully created.')
    

    
    
    
if __name__ == '__main__':
    start_time = time.clock()
    main()
    end_time = time.clock()
    arcpy.AddMessage('Main process is complete. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60))
##    end_time = time.clock()
##    print 'Main process encountered an error. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60)


            
        
        
    
