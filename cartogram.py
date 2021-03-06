import numpy as np
import shapely
import geopandas as gpd
from shapely.geometry import Polygon


def cartogram(arg_polygons, arg_values, itermax=5, max_size_error=1.0001, epsilon=0.01, verbose=False):
    """
    Generate an area equalizing contiguous cartogram based on the algorithm by (J. Oougenik et al., 1985).
    
    Note: The current function does not include interior boundaries when distorting the polygons!
          This is due to shapely's current way of extracting boundary coordinates which make it 
          cumbersome to separate interior points from exterior points.
    
    :param arg_polygons: geopandas.geoseries.GeoSeries Series of shapely.geometry.Polygon objects.
    :param arg_values: (geo)pandas.Series Series of floating point values.
    :param itermax: int (Optional, default=5) Maximum amount of iterations to perform adjusting coordinates.
    :param max_size_error: float (Optional, default=1.0001) A maximum accuracy until terminating the procedure.
    :param epsilon: float (Optional, default=0.01) Scalar to prevent zero division errors.
    :param verbose: bool (Optional, default=False) Whether to print out intermediary progress. 
    
    :returns: geopandas.geoseries.GeoSeries Copy of :arg_polygons: with the adjusted coordinates.
    
    :references: Dougenik, J.A., Chrisman, N.R. and Niemeyer, D.R. (1985), 
                 AN ALGORITHM TO CONSTRUCT CONTINUOUS AREA CARTOGRAMS*. 
                 The Professional Geographer, 37: 75-81. doi:10.1111/j.0033-0124.1985.00075.x 
    
    :see: Implementation of the same algorithm in R (available on CRAN): https://github.com/sjewo/cartogram
    """    
    polygons = arg_polygons.copy().values
    values = arg_values.copy().values
    
    total_value = values.sum()
    mean_size_error = 100
    
    for iteration in range(itermax):
        if mean_size_error < max_size_error:
            break
        
        # This statement unpacks the centroid Point object to np.array and
        # creates a n x 2 matrix of centroid [x, y] coordinates.
        centroids = np.array(list(map(np.array, polygons.centroid)))
        area = polygons.area
        total_area = area.sum()
        
        desired = total_area * values / total_value
        desired[desired == 0] = epsilon  # Prevent zero division.
        radius = np.sqrt(area / np.pi)
        mass = np.sqrt(desired / np.pi) - np.sqrt(area / np.pi)
        
        size_error = np.max([desired, area], axis=0) - np.min([desired, area], axis=0)
        mean_size_error = np.mean(size_error)
        force_reduction_factor = 1 / (1 + mean_size_error)
        
        if verbose:
            print("Mean size error at iteration {}: {}".format(iteration+1, mean_size_error))
        for row, polygon in enumerate(polygons):
            
            # TODO: Possibly include shapely.geometry.Polygon interior coordinates.
            
            # Some coordinates may appear twice, however, they mustn't be removed.
            # These coordinates are also adjusted, but only computed once:
            coordinates = np.matrix(polygon.exterior.coords)    # [[x1, y2], [x2, y2], ...]
            idx = np.unique(coordinates, axis=0)                # Get unique rows
            
            for k in range(len(idx)):
                # Get positions from coordinates for each unique idx.
                coord_idx = np.where((coordinates[:, 0] == idx[k,0]) & (coordinates[:,1] == idx[k, 1]))[0]
                # Only extract one using coord_idx[0] as coord_idx maps duplicate coordinates.
                new_coordinates = coordinates[coord_idx[0],:]  
                
                # Compute coordinate's euclidean distances to all centroids.
                distances = np.sqrt(np.square(centroids - new_coordinates).sum(axis=1))
                distances = np.array(distances).ravel()  # Converts matrix into flat array.
                
                # Compute force vectors
                Fijs = mass * radius / distances
                Fbij = mass * np.square(distances / radius) * (4 - 3 * distances / radius)
                Fijs[distances <= radius] = Fbij[distances <= radius]
                Fijs *= force_reduction_factor / distances
                
                # Find how much "force" must be applied to the coordinates by computing
                # the dot product of the force vector and the centroid deltas.
                new_coordinates += Fijs.dot(new_coordinates - centroids)
                
            # Set the polygon 
            polygons[row] = Polygon(coordinates, holes = polygon.interiors)
            
    return gpd.geoseries.GeoSeries(polygons)
