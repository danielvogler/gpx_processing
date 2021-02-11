"""
Daniel Vogler
gpxProcessing
"""

import gpxpy # pip3 install gpxpy
from haversine import haversine # pip3 install haversine
import numpy as np
from datetime import datetime
from matplotlib import pyplot as plt
from scipy.interpolate import splprep, splev
import similaritymeasures
from datetime import timedelta, datetime

import warnings
warnings.filterwarnings("ignore")

class gpxProcessing:

    ### prepare gpx tracks for dtw matching
    ### find all suitable start/end point combinations
    ### determine shortest segment match
    def dtw_match(self,gold_name,activity_name, min_trkps = 50, radius=7, dtw_threshold=0.2):

        start_time = datetime.now()

        ### load gold standard/baseline segment
        gold = self.gpx_loading(gold_name)
        ### interpolate gold data
        gold_interpolated = self.interpolate(gold)

        ### load activity data to be edited
        trkps = self.gpx_loading(activity_name)
        ### crop activity data to segment length
        gpx_cropped = self.gpx_track_crop(gold, trkps, radius)

        ### find potential start/end trackpoints
        nn_start, nn_start_idx = self.nearest_neighbours(gpx_cropped,gold[:4,0],radius)
        nn_finish, nn_finish_idx = self.nearest_neighbours(gpx_cropped,gold[:4,-1],radius)

        ### initial time
        final_time = timedelta(seconds=1e6)
        ### tested combinations of start/end points
        combinations_tested = 0

        ### possible start point combinations
        for i in nn_start_idx:

            ### possible end point combinations
            for j in nn_finish_idx:

                ### start needs to happen before finish and include minTrkps in between
                if i < j-min_trkps:

                    combinations_tested += 1

                    ### compute DTW between gold and activity
                    dtw, delta_time = self.dtw_computation(gpx_cropped[:,i:j+1],gold_interpolated)

                    ### collect final time and dtw
                    if delta_time < final_time and dtw < dtw_threshold:
                        final_time = delta_time
                        final_dtw = dtw

        print("\nFinal DTW (y): %2.5f"% (final_dtw) )
        print("Final T [s]:  " , (final_time) )

        print("\nTotal execution time:", datetime.now() - start_time)
        print("Total combinations tested:" , (combinations_tested) )
        print("Execution time per combination:" , ((datetime.now() - start_time)/combinations_tested) )

        return final_time, final_dtw


    ### Load gpx file and extract information
    def gpx_loading(self,file_name):

        ### load file
        gpx_data_open = open(file_name)
        gpx_data = gpxpy.parse(gpx_data_open)

        ### initialize lat/lon
        trkp_lat = []
        trkp_lon = []
        trkp_ele = []
        trkp_time = []

        ### load relevant gpx data
        for track in gpx_data.tracks: 
            for segment in track.segments: 
                for i in range(0,len(segment.points)-1):
                    trkp_point = segment.points[i]
                    trkp_lat.append(trkp_point.latitude)
                    trkp_lon.append(trkp_point.longitude)
                    trkp_ele.append(trkp_point.elevation)
                    trkp_time.append(trkp_point.time)

        trkps = np.asarray([trkp_lat, trkp_lon, trkp_ele, trkp_time])

        return trkps


    ### filter gpx data occurring between two points
    def gpx_track_crop(self,gold,gpx_data,radius):

        ### find possible start/end trackpoints
        nn_start, nn_start_idx = self.nearest_neighbours(gpx_data,gold[:4,0],radius)
        print("\nPoints of activity within {}m of gold start: {}".format(radius, len(nn_start_idx) ) )

        nn_finish, nn_finish_idx = self.nearest_neighbours(gpx_data,gold[:4,-1],radius)
        print("Points of activity within {}m of gold finish: {}".format(radius, len(nn_finish_idx) ) )

        ### determine time range for gpx track
        nn_start_earliest = min(nn_start[3])
        nn_finish_latest = max(nn_finish[3])

        ### delete trackpoints outside relevant time range
        indices = [i for i in range(len(gpx_data[3])) if nn_start_earliest <= gpx_data[3,i] <= nn_finish_latest]
        cr_lat   = [gpx_data[0,i] for i in indices]
        cr_lon   = [gpx_data[1,i] for i in indices]
        cr_ele   = [gpx_data[2,i] for i in indices]
        cr_time  = [gpx_data[3,i] for i in indices]
        gpx_cropped = np.asarray([cr_lat, cr_lon, cr_ele, cr_time])

        return gpx_cropped


    ### find nearest neighbouring points of input point
    def nearest_neighbours(self,gpx_data,centroid,radius):

        ### distance (m) of all points to centroid
        distance = [haversine(i, centroid[:2]) * 1000 for i in gpx_data[:4,:][:2].T ]

        ### points within radius distance of centroid
        idx = [int(i) for i, x in enumerate(distance) if x < radius]

        ### check if nearby points were found
        if not idx:
            print("No trackpoints found near centroid\n")
            return -1

        ### lat, lon, ele, time, distance of all nearest neighbours
        lat   = [gpx_data[0,i] for i in idx]
        lon   = [gpx_data[1,i] for i in idx]
        ele   = [gpx_data[2,i] for i in idx]
        time  = [gpx_data[3,i] for i in idx]
        dis   = [distance[i] for i in idx]
        nn = np.asarray([lat, lon, ele, time, dis])

        return nn, idx


    ### dynamic time warping between two gpx-track curves
    def dtw_computation(self,gpx_data,gold):

        ### time difference of start to finish
        delta_time = gpx_data[3][-1] - gpx_data[3][0]

        ### interpolate activity
        gpx_data_interpolated = self.interpolate(gpx_data)

        ### compute dynamic time warping
        dtw, d = similaritymeasures.dtw(gpx_data_interpolated, gold)

        print("\nDTW (y): %2.5f"% (dtw) )
        print("T [s]:  " , (delta_time) )

        return dtw, delta_time


    ### interpolate gpx data along track
    def interpolate(self,gpx_data):

        interpolation_points = 1000

        ### add random noise to avoid duplicates
        data = np.array([(x+np.random.uniform(low=-1e-7, high=1e-7),y+np.random.uniform(low=-1e-7, high=1e-7)) for x,y in zip(gpx_data[0][:], gpx_data[1][:])])

        ### function that interpolates original data
        tck, u = splprep(data.T, u=None, s=0.0, t=10, per=0)

        ### 
        u_new = np.linspace(u.min(), u.max(), interpolation_points)

        ### fit interpolation function to equi-distant data
        lat, lon = splev(u_new, tck, der=0)

        ### only return necessary gpx data
        points = np.zeros((interpolation_points,2))

        # points = np.asarray([lat, lon])
        points[:, 0] = lat
        points[:, 1] = lon

        return points


    ### plot gpx track
    def gpx_plot(self,fig,gpx_data,plot_info,marker_size=500):

        font_size = 30
        plt.rcParams.update({'font.size': font_size})
        plt.scatter(gpx_data[1,:],gpx_data[0,:],s=marker_size,marker=plot_info[1],c=plot_info[2],label=plot_info[0])
        plt.legend(loc='upper left')
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")

        return(fig)
