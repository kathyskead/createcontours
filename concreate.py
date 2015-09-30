import arcpy
import os
##import multiprocessing
import itertools
import time

#variables
workspace = 'c:/Kent_Contour/test/workspace/test.gdb'
main_raster = 'c:/Kent_Contour/test/raw_DEM/DEM.img'
dem = arcpy.sa.Raster(main_raster)
spatial_ref = dem.extent.spatialReference.factoryCode
raster_height = int(dem.height.real)
raster_width = int(dem.width.real)

#output directories and datasets
dem_filled_out = os.path.join(os.path.split(workspace)[0],'dem_filled')
contours_fill_out = os.path.join(workspace,'Contours_fill')
contours_raw_out = os.path.join(workspace,'Contours_raw')
contours_smooth_out = os.path.join(workspace,'Contours_smooth')
contours_final_out = os.path.join(workspace,'Contours_final_clip')
townships_out = os.path.join(workspace,'Townships')
#set topology dataset and error output location
topo_output = contours_final_out
error_output = os.path.join(workspace,'Topology_Errors')

#fishnet variables
outFeature = os.path.join(os.path.split(workspace)[0],'fishnet.shp')
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
#set buffer distance for tiles
buffer_dist = 250

#smooth line variables
#this number is in the same units as the geometry of the feature being smoothed
tolerance = 15
smoothing_method = 'PAEK'

#set location which contains the township boundary tiles
township_tiles_location = 'C:/Kent_Contour/TownrangeSplitBuf'


# set topology rule
rule = 'Must Not Intersect (Line)'




#to get number of tiles (based on raster grid row/column count)
#CAN OPTIONALLY BE DONE MANUALLY
def counter(n):
    for i in range(1,n):
        yield i

def get_factors(n):
    factors = [i for i in counter(n) if n % i == 0]
    print 'The raster grid height/width can be evenly divided by these factors: {0}'.format(factors)
    try:
        result = int(max([f for f in factors if f in range(1,50)]))
        return result
    except:
        print 'Raster grid has no even factors between 1 and 50'



def create_fishnet(number_columns,number_rows):
    arcpy.CreateFishnet_management(outFeature,origin_coord,y_coord,cell_width,
                                   cell_height,number_rows,number_columns,opposite_corner_coord,
                                   labels,template,geometry_type)
    arcpy.AddField_management(outFeature,'Name','TEXT')
    with arcpy.da.UpdateCursor(outFeature,['OID@','Name']) as cursor:
        for oid,name in cursor:
            row = (oid,'Tile_{0:02d}'.format(oid))
            cursor.updateRow(row)

            
def get_tile_names():
    fishnet = outFeature
    with arcpy.da.SearchCursor(fishnet,'Name') as rows:
        name_list = []
        for row in rows:
            name_list.append(row[0])
            del row
        name_list.sort()
    return name_list


def get_tiles():
    fishnet = outFeature
    with arcpy.da.SearchCursor(fishnet,['Name','SHAPE@']) as rows:
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
    fishnet = outFeature
    with arcpy.da.SearchCursor(fishnet,['Name','SHAPE@']) as rows:
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
    name = 'Fill_{0}'.format(os.path.splitext(os.path.split(inras)[1])[0])
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
    name = 'Smooth_{0}'.format(os.path.split(fc)[1])
    output = os.path.join(contours_smooth_out,name)
    arcpy.cartography.SmoothLine(fc,output,smoothing_method,tolerance)

def trim_dangles(fc):
##    arcpy.env.extent = arcpy.Describe(fc).extent
    arcpy.TrimLine_edit(fc,'10 Feet','DELETE_SHORT')


def clip_fcs(name,fc):
##    arcpy.env.extent = arcpy.Describe(fc).extent
    clip_tiles_dict = get_tiles()
    fc_name = 'Clip_{0}'.format(name)
    tile = clip_tiles_dict[name] 
    output = os.path.join(contours_final_out,fc_name)
    arcpy.Clip_analysis(fc,tile,output)


def merge_contours(fcs):
    output = os.path.join(workspace,'Contours_All')
    arcpy.Merge_management(fcs,output)


def clip_to_townships(fc,clipfc):
##    arcpy.env.extent = arcpy.Describe(clipfc).extent
    name = os.path.splitext(os.path.split(clipfc)[1])[0]
    output = os.path.join(townships_out,'T{0}'.format(name))
    arcpy.Clip_analysis(fc,clipfc,output)

def create_topology(fc):
    toponame = '{0}_topo'.format(os.path.split(fc)[1])
    topo_path = os.path.join(topo_output,toponame)
    arcpy.CreateTopology_management(topo_output,toponame)
    arcpy.AddFeatureClassToTopology_management(topo_path, fc, 1)
    arcpy.AddRuleToTopology_management(topo_path,rule,fc)
    arcpy.ValidateTopology_management(topo_path)
    arcpy.ExportTopologyErrors_management(topo_path,error_output,'{0}_errors'.format(os.path.split(fc)[1]))
    
  
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
    print 'Creating directories...'
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
    if not arcpy.Exists(townships_out):
        arcpy.CreateFeatureDataset_management(workspace,'Townships',main_raster)
    if not arcpy.Exists(error_output):
        arcpy.CreateFeatureDataset_management(workspace,'Topology_Errors',main_raster)
        



    #create fishnet atiles and get list of all tiles
    #get fishnet columns and rows
    if not arcpy.Exists(outFeature):
        #columns
        print 'Fishnet setup...'
        print 'Use the following factors to select the number of columns for the fishnet:'
        get_factors(raster_width)
        number_columns = raw_input("Enter the number of columns: ")
        #rows
        print 'Use the following factors to select the number of rows for the fishnet:'
        get_factors(raster_height)
        number_rows = raw_input("Enter the number of rows: ") 
        print 'Creating fishnet...' 
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
    print 'Executing fill on DEM...'
    tiles_buff = get_buffered_tiles()
    for name,tile in tiles_buff.iteritems():
        fill_DEM(main_raster,name,tile)
    for dirpath,dirname,filenames in arcpy.da.Walk(dem_filled_out):
        for fn in filenames:
            tiles_fill.append(os.path.join(dirpath,fn))
    tiles_fill.sort()
                          
    
    #execute contour creation
    print 'Creating contour shapefiles...'   
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
    print 'Creating filled contour shapefiles...'
    for inras in tiles_fill:
        create_filled_contours(inras)
    for dirpath,dirname,filenames in arcpy.da.Walk(contours_fill_out):
        for fn in filenames:
            contour_fill.append(os.path.join(dirpath,fn))
    contour_fill.sort()

    #execute attribute update
    print 'Deleting short contours and updating attribute table with index, intermediate and depression values...'
    for fc,fill in itertools.izip(contour_fcs,contour_fill):
        att_contours(fc,fill)


    #execute smooth lines
    print 'Smoothing contours...'
    for fc in contour_fcs:
        smooth_lines(fc)
    for dirpath,dirname,filenames in arcpy.da.Walk(contours_smooth_out):
        for fn in filenames:
            contour_smooth.append(os.path.join(dirpath,fn))
    contour_smooth.sort()


##    #execute trim dangles 
##    #TODO: Trim line encountered error "Invalid Topology". Possibly memory issue, or need to run "Check/Repair Geometry"
##    print 'Executing trim line to remove dangles...'
##    for fc in contour_smooth:
##        trim_dangles(fc)

##    #reset processing extent to full dataset
##    arcpy.env.extent = dem.extent

    #create dictionary joining tile names to features, and execute final clip
    tile_names = get_tile_names()
    contour_dict = dict(itertools.izip(tile_names,contour_smooth))
    print 'Executing final clip to remove edge effects...'
    for name,fc in contour_dict.iteritems():
        clip_fcs(name,fc)

    #run topology and export errors
    print 'Creating topology and validating...'
    for dirpath,dirname,filenames in arcpy.da.Walk(contours_final_out):
        for fn in filenames:
            contour_final.append(os.path.join(dirpath,fn))
    map(create_topology,contour_final)

    #merge errors, and get total error count
    print 'Merging point errors and getting total count...'
    for dirpath,dirname,filenames in arcpy.da.Walk(error_output,datatype='FeatureClass',type='Point'):
        for fn in filenames:
            point_errors.append(os.path.join(dirpath,fn))
    for dirpath,dirname,filenames in arcpy.da.Walk(error_output,datatype='FeatureClass',type='Polyline'):
        for fn in filenames:
            line_errors.append(os.path.join(dirpath,fn))
    get_total_errors(point_errors,line_errors)

    
    #merge contour tiles into full contour dataset
    print 'Merging contour tiles into single dataset...'
    merge_contours(contour_final)

    #clip to township boundaries
    print 'Clipping dataset to township boundaries...'
    fc = '{0}/Contours_All'.format(workspace)
    clipfcs = []
    for dirpath,dirname,filenames in arcpy.da.Walk(township_tiles_location):
        for fn in filenames:
            clipfcs.append(os.path.join(dirpath,fn))
    for clipfc in clipfcs:
        clip_to_townships(fc,clipfc)


    print 'Final contour datasets successfully created.'
    

    
    
    
if __name__ == '__main__':
    start_time = time.clock()
    main()
    end_time = time.clock()
    print 'Main process is complete. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60)
##    end_time = time.clock()
##    print 'Main process encountered an error. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60)


            
        
        
    
