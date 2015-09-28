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
#fishnet variables
outFeature = '{0}/fishnet.shp'.format(os.path.split(workspace)[0])
origin_coord = '{0} {1}'.format(dem.extent.lowerLeft.X,dem.extent.lowerLeft.Y)
y_coord = '{0} {1}'.format(dem.extent.lowerLeft.X,dem.extent.upperLeft.Y)
cell_width = '0'
cell_height = '0'
number_rows = '5'
number_columns = '3'
opposite_corner_coord = '{0} {1}'.format(dem.extent.upperRight.X,dem.extent.upperRight.Y)
labels = 'NO_LABELS'
#extent is set by origin and opposite corner coords -- no need to use template 
template = '#'
geometry_type = 'POLYGON'

#smooth line variables
#this number is in the same units as the geometry of the feature being smoothed
tolerance = 15 
smoothing_method = 'PAEK'

#set location which contains the township boundary tiles
township_tiles_location = 'C:/Kent_Contour/TownrangeSplitBuf'

#set topology dataset and error output location
topo_output = '{0}/Contours_final_clip'.format(workspace)
error_output = '{0}/Topology_Errors'.format(workspace)
# set topology rule
rule = 'Must Not Intersect (Line)'



def create_fishnet():
    arcpy.CreateFishnet_management(outFeature,origin_coord,y_coord,cell_width,
                                   cell_height,number_rows,number_columns,opposite_corner_coord,
                                   labels,template,geometry_type)
    arcpy.AddField_management(outFeature,'Name','TEXT')
    with arcpy.da.UpdateCursor(outFeature,['OID@','Name']) as cursor:
        for oid,name in cursor:
            row = (oid,'Tile_{0:02d}'.format(oid))
            cursor.updateRow(row)

def get_tiles():
    fishnet = '{0}/fishnet.shp'.format(os.path.split(workspace)[0])
    with arcpy.da.SearchCursor(fishnet,['Name','SHAPE@']) as rows:
        tiles = {}
        array = arcpy.Array()
        for row in rows:
            name = row[0]
            extent = row[1].extent
            array.add(extent.lowerLeft)
            array.add(extent.lowerRight)
            array.add(extent.upperRight)
            array.add(extent.upperLeft)
            tiles[name] = arcpy.Polygon(array)
            array.removeAll()
            del row
        del array
    return tiles
    
def get_buffered_tiles():
    fishnet = '{0}/fishnet.shp'.format(os.path.split(workspace)[0])
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
            tiles_buff[name] = arcpy.Polygon(array).buffer(50)
            array.removeAll()
            del row
        del array
    return tiles_buff
        
    
def fill_DEM(inras,name,tile):
##    name = os.path.split(inras)[1]
    arcpy.env.extent = tile.extent
    outFill = arcpy.sa.Fill(inras)
    outFill.save('{0}/dem_filled/{1}'.format(os.path.split(workspace)[0],name))
    

def create_contours(inras,name,tile):
    arcpy.env.extent = tile.extent
    output = '{0}/Contours_raw/{1}'.format(workspace,name)
    arcpy.sa.Contour(inras,output,2,0)

def create_filled_contours(inras):
    arcpy.env.extent = arcpy.Raster(inras).extent
    name = 'Fill_{0}'.format(os.path.splitext(os.path.split(inras)[1])[0])
    output = '{0}/Contours_fill/{1}'.format(workspace,name)
    arcpy.sa.Contour(inras,output,2,0)
    

def att_contours(fc,filled):
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
    arcpy.env.extent = arcpy.Describe(fc).extent
    name = 'Smooth_{0}'.format(os.path.split(fc)[1])
    arcpy.cartography.SmoothLine(fc,'{0}/Contours_smooth/{1}'.format(workspace,name),smoothing_method,tolerance)

def trim_dangles(fc):
    arcpy.env.extent = arcpy.Describe(fc).extent
    arcpy.TrimLine_edit(fc,'10 Feet','DELETE_SHORT')

# clips based oon negative buffer on buffered tiles
                   #TODO: fix this
def clip_fcs(fc):
    name = 'Clip_{0}'.format(os.path.split(fc)[1])
    tile_name = os.path.split(fc)[1][:6:-1]
    tile = tiles[tile_name]
##    desc = arcpy.Describe(fc)
##    extent = desc.extent
##    pnt_array = arcpy.Array()   
##    pnt_array.add(extent.lowerLeft)
##    pnt_array.add(extent.lowerRight)
##    pnt_array.add(extent.upperRight)
##    pnt_array.add(extent.upperLeft)
##    clip_poly = arcpy.Polygon(pnt_array).buffer(-150)
    arcpy.Clip_analysis(fc,tile,'{0}/Contours_final_clip/{1}'.format(workspace,name))




def merge_contours(fcs):
    arcpy.Merge_management(fcs,'{0}/Contours_All'.format(workspace))


def clip_to_townships(fc,clipfc):
    arcpy.Clip_analysis(fc,clipfc,'{0}/Townships/T{1}'.format(workspace,os.path.splitext(os.path.split(clipfc)[1])[0]))

def create_topology(fc):
    toponame = '{0}_topo'.format(os.path.split(fc)[1])
    topo_path = '{0}/{1}'.format(topo_output,toponame)
    arcpy.CreateTopology_management(topo_output,toponame)
    arcpy.AddFeatureClassToTopology_management(topo_path, fc, 1)
    arcpy.AddRuleToTopology_management(topo_path,rule,fc)
    arcpy.ValidateTopology_management(topo_path)
    arcpy.ExportTopologyErrors_management(topo_path,error_output,'{0}_errors'.format(os.path.split(fc)[1]))
    
  
def get_total_errors(point_errors,line_errors):
    total_line_errors = '{0}/All_Line_Errors'.format(error_output)
    total_point_errors = '{0}/All_Point_Errors'.format(error_output)
    arcpy.Merge_management(point_errors,total_point_errors)
    arcpy.Merge_management(line_errors,total_line_errors)
    point_count = arcpy.GetCount_management(total_point_errors)
    line_count = arcpy.GetCount_management(total_line_errors)
    arcpy.Rename_management(total_line_errors,'{0}_{1}'.format(total_line_errors,line_count))
    arcpy.Rename_management(total_point_errors,'{0}_{1}'.format(total_point_errors,point_count))
    

def main():
    #set workspace
    #arcpy.env.workspace = workspace
    #set output coord. system
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(spatial_ref)
    #set overwrite status
    arcpy.env.overwriteOutput = True
    #check out spatial analyst extension
    arcpy.CheckOutExtension("Spatial")
    
    #make all needed directories and datasets
##    print 'Creating directories...'
##    os.mkdir('{0}/dem_tiles'.format(os.path.split(workspace)[0]))
##    os.mkdir('{0}/dem_tiles_buff'.format(os.path.split(workspace)[0]))
##    os.mkdir('{0}/dem_filled'.format(os.path.split(workspace)[0]))
##    arcpy.CreateFeatureDataset_management(workspace,'Townships',main_raster)
##    arcpy.CreateFeatureDataset_management(workspace,'Contours_raw',main_raster)
##    arcpy.CreateFeatureDataset_management(workspace,'Contours_fill',main_raster)
##    arcpy.CreateFeatureDataset_management(workspace,'Contours_smooth',main_raster)
##    arcpy.CreateFeatureDataset_management(workspace,'Contours_final_clip',main_raster)
##    arcpy.CreateFeatureDataset_management(workspace,'Topology_Errors',main_raster)

    #create the raster tiles and get list of all tiles
##    print 'Creating fishnet...'
##    create_fishnet()

    tiles = get_tiles()
    tiles_buff = get_buffered_tiles()

    tiles_fill = sorted([])
    contour_fcs = sorted([])
    contour_fill = sorted([])
    contour_smooth = sorted([])
    contour_final = sorted([])
    point_errors = []
    line_errors = []
##                      
##    for dirpath,dirname,filenames in arcpy.da.Walk('{0}/dem_tiles_buff'.format(os.path.split(workspace)[0])):
##        for fn in filenames:
##            tiles_buff.append(os.path.join(dirpath,fn))
##    for dirpath,dirname,filenames in arcpy.da.Walk('{0}/dem_tiles'.format(os.path.split(workspace)[0])):
##        for fn in filenames:
##            tiles.append(os.path.join(dirpath,fn))

   
    #execute fill
##    print 'Executing fill on DEM...'
####    map(fill_DEM,tiles_buff)
##    for name,tile in tiles_buff.iteritems():
##        fill_DEM(main_raster,name,tile)
    for dirpath,dirname,filenames in arcpy.da.Walk('{0}/dem_filled'.format(os.path.split(workspace)[0])):
        for fn in filenames:
            tiles_fill.append(os.path.join(dirpath,fn))
##                          
    
    #execute contour creation
    print 'Creating contour shapefiles...'   
    for name,tile in tiles_buff.iteritems(): 
        create_contours(main_raster,name,tile)
    for dirpath,dirname,filenames in arcpy.da.Walk('{0}/Contours_raw'.format(workspace)):
        for fn in filenames:
            contour_fcs.append(os.path.join(dirpath,fn))
    for fc in contour_fcs:
        arcpy.AddField_management(fc,'Type','TEXT')


    #execute filled contour creation
    print 'Creating filled contour shapefiles...'
    for inras in tiles_fill:
        create_filled_contours(inras)
    for dirpath,dirname,filenames in arcpy.da.Walk('{0}/Contours_fill'.format(workspace)):
        for fn in filenames:
            contour_fill.append(os.path.join(dirpath,fn))

    #execute attribute update
    print 'Deleting short contours and updating attribute table with index, intermediate and depression values...'
    for fc,fill in itertools.izip(contour_fcs,contour_fill):
        att_contours(fc,fill)


##    #execute smooth lines
##    print 'Smoothing contours...'
##    for fc in contour_fcs:
##        smooth_lines(fc)
##    for dirpath,dirname,filenames in arcpy.da.Walk('{0}/Contours_smooth'.format(workspace)):
##        for fn in filenames:
##            contour_smooth.append(os.path.join(dirpath,fn))
    

##    #execute trim dangles and final clip
##    #TODO: Trim line encountered error "Invalid Topology". Possibly memory issue, or need to run "Check/Repair Geometry"
##    print 'Executing trim line to remove dangles...'
####    for fc in contour_smooth:
####        trim_dangles(fc)
##    print 'Executing final clip to remove edge effects...'
####    for fc,tile in itertools.izip(contour_smooth,tiles):
##    for fc in contour_smooth:
##        clip_fcs(fc)
##
##    #run topology and export errors
##    print 'Creating topology and validating...'
##    for dirpath,dirname,filenames in arcpy.da.Walk('{0}/Contours_final_clip'.format(workspace)):
##        for fn in filenames:
##            contour_final.append(os.path.join(dirpath,fn))
##    map(create_topology,contour_final)
##
##    #merge errors, and get total error count
##    print 'Merging point errors and getting total count...'
##    for dirpath,dirname,filenames in arcpy.da.Walk(error_output,datatype='FeatureClass',type='Point'):
##        for fn in filenames:
##            point_errors.append(os.path.join(dirpath,fn))
##    for dirpath,dirname,filenames in arcpy.da.Walk(error_output,datatype='FeatureClass',type='Polyline'):
##        for fn in filenames:
##            line_errors.append(os.path.join(dirpath,fn))
##    get_total_errors(point_errors,line_errors)

    
##    #merge contour tiles into full contour dataset
##    print 'Merging contour tiles into single dataset...'
##    merge_contours(contour_final)
##
##    #clip to township boundaries
##    print 'Clipping dataset to township boundaries...'
##    fc = '{0}/Contours_All'.format(workspace)
##    clipfcs = []
##    for dirpath,dirname,filenames in arcpy.da.Walk(township_tiles_location):
##        for fn in filenames:
##            clipfcs.append(os.path.join(dirpath,fn))
##    for clipfc in clipfcs:
##        clip_to_townships(fc,clipfc)
##
##
##    print 'Final contour datasets successfully created.'
    

    
    
    
if __name__ == '__main__':
    start_time = time.clock()
    main()
    end_time = time.clock()
    print 'Main process is complete. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60)
##    end_time = time.clock()
##    print 'Main process encountered an error. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60)


            
        
        
    
