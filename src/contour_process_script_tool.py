import arcpy
import os
import sys
import shutil
##import multiprocessing
import itertools
import time


###stand-alone script variables. This script can be used a stand-alone program by setting the following variables.
##workspace = r'C:\Users\patrizio\Projects\Contouring\Test\test_workspace.gdb'
##main_raster = r'C:\Users\patrizio\Projects\Contouring\Test\DEM\DEM_test.tif'
###set buffer distance for tiles
##buffer_dist = 100
###smooth line tolerance--this number is in the same units as the geometry of the feature being smoothed. If
### 'BEZIER_INTERPOLATION' is selected as smoothing method, set this to '0'
##tolerance = 15
###set smoothing method: 'PAEK' or 'BEZIER_INTERPOLATION'
##smoothing_method = 'PAEK'
##
###TODO:Implement console raw input for number of columns/rows (use updateParams code from script tool validation code)
##number_columns = '6'
##number_rows = '1'

#get parameter inputs
workspace = arcpy.GetParameterAsText(0)
main_raster = arcpy.GetParameterAsText(1)
buffer_dist = float(arcpy.GetParameterAsText(2))
contour_interval = float(arcpy.GetParameterAsText(3))
smoothing_method = arcpy.GetParameterAsText(4)
tolerance = arcpy.GetParameterAsText(5)
number_columns = arcpy.GetParameterAsText(6)
number_rows = arcpy.GetParameterAsText(7)

if smoothing_method == 'BEZIER_INTERPOLATION':
    tolerance = 0

#display inputs
arcpy.AddMessage('System version: {0}'.format(sys.version))
arcpy.AddMessage('Workspace geodatabase: {0}'.format(workspace))
arcpy.AddMessage('Input DEM: {0}'.format(main_raster))
arcpy.AddMessage('Processing Buffer: {0}'.format(buffer_dist))
arcpy.AddMessage('Contour Interval: {0}'.format(contour_interval))
arcpy.AddMessage('Smoothing Method: {0}'.format(smoothing_method))
arcpy.AddMessage('Smoothing Tolerance: {0}'.format(tolerance))
arcpy.AddMessage('Fishnet Columns: {0}'.format(number_columns))
arcpy.AddMessage('Fishnet Rows: {0}'.format(number_rows))

# This code was used in the script tool validation code to generate a list of numbers for fishnet columns and rows,
# which are multiples of the total height/width of the DEM, to ensure alignment of the tiles with the DEM.
# Deprecated, in favor of setting snap raster for initial tile processing.

  # def updateParameters(self):
    # """Modify the values and properties of parameters before internal
    # validation is performed.  This method is called whenever a parameter
    # has been changed."""

    # dem = arcpy.sa.Raster(str(self.params[1].value))
    # raster_height = int(dem.height.real)
    # raster_width = int(dem.width.real)
    # rows_list = sorted(list((i for i in range(1,raster_height) if raster_height % i == 0)))
    # columns_list = sorted(list((i for i in range(1,raster_width) if raster_width % i == 0)))
    # self.params[5].filter.list = columns_list
    # self.params[6].filter.list = rows_list
    # del dem
    # return


#get DEM spatial ref and dimensions
dem = arcpy.sa.Raster(main_raster)
spatial_ref = dem.extent.spatialReference.factoryCode
##raster_height = int(dem.height.real)
##raster_width = int(dem.width.real)


#output directories and datasets
##dem_filled_out = os.path.join(os.path.dirname(workspace),'dem_filled')
dem_filled_out = "in_memory"
contours_fill_out = "in_memory"
contours_raw_out = "in_memory"
contours_smooth_out = "in_memory"
contours_final_out = os.path.join(workspace,'Contours_final')
#set topology dataset and error output location
topo_output = contours_final_out
##error_output = "in_memory"
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

# helper function to list datasets
def list_datasets(location, datatype=None, subtype=None, exclusion=None):
    ''' (str[,datatype = str[,type = str][,exclusion = str]) -> list
    Takes an input string of the directory (or workspace)
    containing the datasets and recursively returns all filepaths into a list.
    Optional datatype,subtype and exlusion args can be set to limit the results.
    If you want to exclude a folder, set the 'exclusion' parameter to the directory name (or list of names).
    You may also set 'datatype' and 'type' parameters according to the arcpy.da.Walk syntax (http://resources.arcgis.com/EN/HELP/MAIN/10.2/index.html#//018w00000023000000")


    >>> get_features("C:/workspace",datatype = "FeatureClass",type = "Polygon",exclusions = "Projected")
    >>> [list of all polygon feature classes in 'C:/workspace', excluding all those in a subdirectory named "Projected"]
    '''
    result = []
    if exclusion:
        for dirpath,dirnames,files in arcpy.da.Walk(location,datatype = datatype,type = subtype):
            if exclusion in dirnames:
                dirnames.remove(exclusion)
            for filename in files:
                result.append(os.path.join(dirpath,filename))
    else:
        for dirpath,dirnames,files in arcpy.da.Walk(location,datatype = datatype,type = subtype):
            for filename in files:
                result.append(os.path.join(dirpath,filename))
    return result

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
    arcpy.env.snapRaster = inras
    output = os.path.join(output_dir,"fill_{0}".format(name))
    outFill = arcpy.sa.Fill(inras)
    outFill.save(output)
    return output


def create_contours(inras,name,tile,output_dir,contour_interval):
    ''' (raster,string,polygon object,path string)->output path string
    Sets processing extent to polygon object extent.
    Executes Contour geoprocess on raster dataset.
    Saves output according to name and output_dir parameters.
    Returns output path string.
    '''
    arcpy.env.extent = tile.extent
    arcpy.env.snapRaster = inras
    output = os.path.join(output_dir,name)
    arcpy.sa.Contour(inras,output,contour_interval,0)
    return output

def create_filled_contours(inras,output_dir,contour_interval):
    ''' (raster,path string) -> output path string
    Executes Contour geoprocess on raster dataset.
    Outputs shapefile with prefix "Fill" according to the name of the input raster and output_dir parameter.
    Returns output path string.
    '''

    name = 'Fill_{0}'.format(os.path.splitext(os.path.basename(inras))[0])
    output = os.path.join(output_dir,name)
    arcpy.sa.Contour(inras,output,contour_interval,0)
    return output


def att_contours(fc,filled):
    ''' (feature class, feature class) -> None
    Updates attribute table and deletes features less than 100 in length.
    Attributes each feature with contour type: Intermediate,Index,Depression.
    Gets depression contour type by selecting all contours which do not intersect the
    filled contours. These are the depression contours.
    Returns none.
    '''

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
    arcpy.AddField_management('contour_lyr','Length','DOUBLE')
    arcpy.CalculateField_management('contour_lyr','Length','!shape.length@feet!','PYTHON')
##    arcpy.AddMessage("Selecting contours for {0} less than 100".format(fc))
##    arcpy.SelectLayerByAttribute_management('contour_lyr','NEW_SELECTION','Shape_Length < 100')
    arcpy.SelectLayerByAttribute_management('contour_lyr','NEW_SELECTION','Length < 100')
##    arcpy.AddMessage("Deleting...")
    arcpy.DeleteFeatures_management('contour_lyr')
##    arcpy.AddMessage("Clear selection")
    arcpy.SelectLayerByAttribute_management('contour_lyr','CLEAR_SELECTION')
##    arcpy.AddMessage("Select contours that intersect filled contours")
    arcpy.SelectLayerByLocation_management('contour_lyr','INTERSECT',filled,'','NEW_SELECTION')
##    arcpy.AddMessage("Switch selection")
    arcpy.SelectLayerByAttribute_management('contour_lyr','SWITCH_SELECTION')
##    arcpy.AddMessage("Calculate field for those contours as Depression")
    arcpy.CalculateField_management('contour_lyr','Type','"Depression"','PYTHON_9.3')
##    arcpy.AddMessage("Clear selection")
    arcpy.SelectLayerByAttribute_management('contour_lyr','CLEAR_SELECTION')
##    arcpy.AddMessage("Claculate field to attribute contour types")
    arcpy.CalculateField_management('contour_lyr','Type',expression,'PYTHON_9.3',codeblock)
    arcpy.DeleteField_management('contour_lyr','Length')
    arcpy.Delete_management('contour_lyr')
    return None



def smooth_lines(fc,output_dir):
    '''(feature class,path string)-> output path string
    Takes a feature class and output path string as inputs.
    Executes Smoothline geoprocess on feature class.
    Saves output prefixed with "Smooth" to output_dir.
    Returns output path string.
    '''

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
    #set output coord. system
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(spatial_ref)
    #set overwrite status
    arcpy.env.overwriteOutput = True
    #check out spatial analyst extension
    arcpy.CheckOutExtension("Spatial")

    #make all needed directories and datasets
    arcpy.AddMessage('Creating directories...')
##    if arcpy.Exists(dem_filled_out):
##        shutil.rmtree(dem_filled_out)
##    os.mkdir(dem_filled_out)
##    if arcpy.Exists(contours_raw_out):
##        arcpy.Delete_management(contours_raw_out)
##    arcpy.CreateFeatureDataset_management(workspace,'Contours_raw',main_raster)
##    if arcpy.Exists(contours_fill_out):
##        arcpy.Delete_management(contours_fill_out)
##    arcpy.CreateFeatureDataset_management(workspace,'Contours_fill',main_raster)
##    if arcpy.Exists(contours_smooth_out):
##        arcpy.Delete_management(contours_smooth_out)
##    arcpy.CreateFeatureDataset_management(workspace,'Contours_smooth',main_raster)
    if arcpy.Exists(contours_final_out):
        arcpy.Delete_management(contours_final_out)
    arcpy.CreateFeatureDataset_management(workspace,'Contours_final',main_raster)
    if arcpy.Exists(error_output):
        arcpy.Delete_management(error_output)
    arcpy.CreateFeatureDataset_management(workspace,'Topology_Errors',main_raster)

    #create fishnet tiles and get list of all tiles
    #get fishnet columns and rows
    arcpy.AddMessage('Creating fishnet...')
    create_fishnet(number_columns,number_rows)

    # initialize feature class lists
    tiles = get_final_tiles(fishnet_out)
    tiles_buff = get_buffered_tiles(fishnet_out,buffer_dist)
    point_errors = []
    line_errors = []

                  
    for name,tile in tiles_buff.iteritems():
        arcpy.AddMessage("Beginning contour processing on {0}...".format(name))
        #execute fill using buffered tile as processing extent
        arcpy.AddMessage('Creating filled DEM tile...')
        try:
            dem_fill = fill_DEM(main_raster,name,tile,dem_filled_out)
        except Exception as e:
            arcpy.AddWarning("Encountered error while filling DEM: {0}".format(e))
            continue
        
        #reset processing extent to full dataset
        arcpy.env.extent = dem.extent
        
        #execute filled contour creation using filled DEM
        arcpy.AddMessage('Creating filled contours...')
        try:
            contour_fill = create_filled_contours(dem_fill,contours_fill_out,contour_interval)
        except Exception as e:
            arcpy.AddWarning('Encountered problem with raster dataset: {0}. Possible empty dataset and can be ignored.'.format(e))
            continue

        #execute contour creation using buffered tile as processing extent
        arcpy.AddMessage('Creating normal contours...' )
        try:
            contour_raw = create_contours(main_raster,name,tile,contours_raw_out,contour_interval)
        except Exception as e:
            arcpy.AddWarning("Encountered error while creating normal contours: {0}".format(e))
            continue
        
        # add contour type field
        try:
            arcpy.AddField_management(contour_raw,'Type','TEXT')
        except Exception as e:
            arcpy.AddWarning("Encountered error adding new field to contour feature class: {0}".format(e))
            continue

        #reset processing extent to full dataset
        arcpy.env.extent = dem.extent

        #execute attribute update
        arcpy.AddMessage('Deleting short contours and updating attribute table with index, intermediate and depression values...')
        try:
            att_contours(contour_raw,contour_fill)
        except Exception as e:
            arcpy.AddWarning("Encountered problem while updating attribute table: {0}".format(e))
            continue

        #execute smooth lines
        arcpy.AddMessage('Smoothing contours...')
        try:
            contour_smoothed = smooth_lines(contour_raw,contours_smooth_out)
        except Exception as e:
            arcpy.AddWarning("Encountered problem while smoothing contours: {0}".format(e))
            continue

        # execute final clip
        arcpy.AddMessage('Executing final clip to remove edge effects...')
        clip_fc = tiles[name]
        try:
            contour_clipped = clip_fcs(contour_smoothed,clip_fc,name,contours_final_out)
        except Exception as e:
            arcpy.AddWarning("Encountered error while clipping: {0}".format(e))
            continue

        # clear in_memory workspace
        arcpy.Delete_management("in_memory")

        #run topology and export errors
        arcpy.AddMessage('Creating topology and validating...')
        try:
            create_topology(contour_clipped,topo_output,rule,error_output)
        except Exception as e:
            arcpy.AddWarning("Encountered error while creating topology: {0}".format(e))
            continue

    #merge errors, and get total error count
    ## TODO: export errors to in_memory workspace after creating topology. keep track of paths in lists. iterate through error list to merge only
    ## line errors and point errors
    try:
        arcpy.AddMessage('Merging point errors and getting total count...')
        point_errors = list_datasets(error_output,datatype='FeatureClass',subtype='Point')
        line_errors = list_datasets(error_output,datatype='FeatureClass',subtype='Polyline')
        point_total,line_total = get_total_errors(point_errors,line_errors,error_output)
        arcpy.AddMessage('Total topology errors: {0} point errors, {1} line errors'.format(point_total,line_total))
    except Exception as e:
        arcpy.AddWarning("Encountered error while reporting number of topology errors: {0}".format(e))

    arcpy.AddMessage("Final contour datasets successfully created.")

        
        
if __name__ == '__main__':
    start_time = time.clock()
    main()
    end_time = time.clock()
    arcpy.AddMessage('Main process is complete. Time elapsed: {0:.2f} minutes'.format((end_time - start_time)/60))
    end_time = time.clock()

