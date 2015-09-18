import arcpy
##import numpy
import os
import multiprocessing

#variables
workspace = 'c:/Kent_Contour/RSGIS/test.gdb'
main_raster = 'c:/Kent_County_MI_LiDAR/DEM/741461.img'
dem = arcpy.sa.Raster(main_raster)
raster_height = int(dem.height.real)
raster_width - int(dem.width.real)
spatial_ref = dem.extent.spatialReference.factoryCode
outFeature = '{0}/fishnet'.format(workspace)
origin_coord = '{0} {1}'.format(dem.extent.lowerLeft.X,dem.extent.lowerLeft.Y)
y_coord = '{0} {1}'.format(dem.extent.lowerLeft.X,dem.extent.upperLeft.Y)
cell_width = '0'
cell_height = '0'
number_rows = '6'
number_columns = '6'
opposite_corner_coord = '{0} {1}'.format(dem.extent.upperRight.X,dem.extent.upperRight.Y)
labels = 'NO LABELS'
#extent is set by origin and opposite corner coords -- no need to use template 
template = '#'
geometry_type = 'POLYGON'

#split raster variables
#set the tile dimensions
number_tiles = '6 6'
#set amount of cell overlap (pixels)
overlap = '150'

#to get number or rows and columns of output fishnet (based on raster grid row/column count)
#CAN OPTIONALLY BE DONE MANUALLY
def counter(n):
    for i in range(1,n):
        yield i

def get_factors(n):
    factors = [i for i in counter(n) if n % i == 0]
    print 'The raster grid height/width can be evenly divided by these factors: {0}'.format(factors)
    try:
        result = int(max([f for f in factors if f in range(3,8)]))
        return result
    except:
        print 'Raster grid has no even factors between 3 and 7'
    
def create_raster_tiles():
    arcpy.SplitRaster_management(raster,'c:/Kent_Contour/test/dem_tiles_buff','Tile_buf_','NUMBER_OF_TILES',"TIFF","BILINEAR",number_tiles,'#',overlap,'PIXELS')
    arcpy.SplitRaster_management(raster,'c:/Kent_Contour/test/dem_tiles','Tile_','NUMBER_OF_TILES',"TIFF","BILINEAR",number_tiles,'#','#','PIXELS')

def create_fill_DEM(ras):
    outFill = arcpy.sa.Fill(ras)
    outFill.save('{0}/dem_filled/{1}_fill'.format(os.path.split(workspace)[0],os.path.splitext(ras)[0]))

def create_contours(ras,output):
    arcpy.sa.Contour(ras,output,2,0)
    
    

##def create_tiles():
##    arcpy.CreateFishnet_management(outFeature,origin_coord,y_coord,cell_width,
##                                   cell_height,number_rows,number_columns,opposite_corner_coord,
##                                   labels,template,geometry_type)
##    arcpy.AddField_management(outFeature,'Name','TEXT')
##    with arcpy.da.UpdateCursor(outFeature,['OID@','Name']) as cursor:
##        for oid,name in cursor:
##            row = (oid,'Tile_{0:02d}'.format(oid)
##            cursor.updateRow(row)

    
                               
        
        
    



def main():
    #set workspace
    arcpy.env.workspace = workspace
    #set output coord. system
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(spatial_ref)
    #set overwrite status
    arcpy.env.overwriteOutput = True
    #check out spatial analyst extension
    arcpy.CheckOutExtension("Spatial")
    
    #make all needed directories and datasets
    os.mkdir('{0}/dem_tiles'.format(os.path.split(workspace)[0]))
    os.mkdir('{0}/dem_tiles_buff'.format(os.path.split(workspace)[0]))
    os.mkdir('{0}/dem_filled'.format(os.path.split(workspace)[0]))
    contour_out = arcpy.CreateFeatureDataset_management(workspace,'Contours_2ft',main_raster)
    contour_fill_out = arcpy.CreateFeatureDataset_management(workspace,'Contours_2ft_fill',main_raster)
    


    #create the raster tiles and get list of all tiles
    create_raster_tiles()
    tiles_buff = []
    tiles = []
    for dirpath,dirname,filenames in arcpy.da.Walk('C:/Kent_Contour/RSGIS/dem_tiles_buff')
        for fn in filenames:
            tiles_buff.append(os.path.join(dirpath,fn))
    for dirpath,dirname,filenames in arcpy.da.Walk('C:/Kent_Contour/RSGIS/dem_tiles')
        for fn in filenames:
            tiles.append(os.path.join(dirpath,fn))

    #execute functions
    #TODO: Implement multiprocessing here
    map(create_fill_DEM,tiles_buff)
    
    
    


if __name__ == '__main__':
    main()
    


            
        
        
    
