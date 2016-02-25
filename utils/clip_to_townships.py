#!/usr/bin/env python
import arcpy, os

# Run this script to clip a contour feature class for an entire county to buffered township boundaries, creating seperate features for each township

####################################
### SET THE FOLLOWING PARAMETERS ###

# The township polygon shapefile
TWNSHIP_FILE = r'C:\Users\patrizio\Projects\Contours\Gratiot_Contours\TownshipBoundary\Townships.shp'

# The name of the field in the township shapefile which contains the township names(or other unique values which will be used to name the output tiles)
TWNSHIP_NAME_FIELD = "TWNRNG"

#The input polyline contour feature
INPUT_FEATURE = r'C:\Users\patrizio\Projects\Contours\Gratiot_Contours\Gratiot_Contours_FINAL.gdb\Gratiot_Contours_2ft'

# The output location
OUTPUT_DIR = r'C:\Users\patrizio\Projects\Contours\Gratiot_Contours\Gratiot_Contours_FINAL.gdb\Townships'

# The buffer distance for the township boundaries
BUFFER_DIST = 1000

####################################

def main():
    print "Starting process..."
    twnships = TWNSHIP_FILE
    twnship_sr = arcpy.Describe(TWNSHIP_FILE).spatialReference.exporttostring()
    input_sr = arcpy.Describe(INPUT_FEATURE).spatialReference.exporttostring()
    if twnship_sr != input_sr:
        twnship_reproj = os.path.join(os.path.dirname(TWNSHIP_FILE),"Townships_reproj.shp")
        arcpy.Project_management(TWNSHIP_FILE,twnship_reproj,INPUT_FEATURE)
        twnships = twnship_reproj
    
    with arcpy.da.SearchCursor(twnships,[TWNSHIP_NAME_FIELD,"SHAPE@"]) as cursor:
        for row in cursor:
            out_feature = os.path.join(OUTPUT_DIR,"T{0}".format(row[0]))
            try:
                print "Creating buffered township tile: {0}".format(out_feature)
                clip_poly = row[1].buffer(BUFFER_DIST)
            except Exception as e:
                print e
            try:
                print "Clipping..."
                arcpy.Clip_analysis(INPUT_FEATURE,clip_poly,out_feature)
            except Exception as e:
                print e
    print "Finished clipping"

if __name__ == "__main__":
    main()
