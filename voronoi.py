from scipy.spatial import Voronoi, voronoi_plot_2d
import numpy as np
import pandas as pd
import matplotlib
import sys,os,argparse
from biopandas.mol2 import PandasMol2
import matplotlib.pyplot as plt

def voronoi_finite_polygons_2d(vor, radius=None):
    """
    Reconstruct infinite voronoi regions in a 2D diagram to finite
    regions.

    Parameters
    ----------
    vor : Voronoi
        Input diagram
    radius : float, optional
        Distance to 'points at infinity'.

    Returns
    -------
    regions : list of tuples
        Indices of vertices in each revised Voronoi regions.
    vertices : list of tuples
        Coordinates for revised Voronoi vertices. Same as coordinates
        of input vertices, with 'points at infinity' appended to the
        end.
        
    Source
    -------
    Copied from https://gist.github.com/pv/8036995 
    """

    if vor.points.shape[1] != 2:
        raise ValueError("Requires 2D input")

    new_regions = []
    new_vertices = vor.vertices.tolist()

    center = vor.points.mean(axis=0)
    if radius is None:
        radius = vor.points.ptp().max()*2

    # Construct a map containing all ridges for a given point
    all_ridges = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    # Reconstruct infinite regions
    for p1, region in enumerate(vor.point_region):
        vertices = vor.regions[region]

        if all(v >= 0 for v in vertices):
            # finite region
            new_regions.append(vertices)
            continue

        # reconstruct a non-finite region
        ridges = all_ridges[p1]
        new_region = [v for v in vertices if v >= 0]

        for p2, v1, v2 in ridges:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                # finite ridge: already in the region
                continue

            # Compute the missing endpoint of an infinite ridge

            t = vor.points[p2] - vor.points[p1] # tangent
            t /= np.linalg.norm(t)
            n = np.array([-t[1], t[0]])  # normal

            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, n)) * n
            far_point = vor.vertices[v2] + direction * radius

            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())

        # sort region counterclockwise
        vs = np.asarray([new_vertices[v] for v in new_region])
        c = vs.mean(axis=0)
        angles = np.arctan2(vs[:,1] - c[1], vs[:,0] - c[0])
        new_region = np.array(new_region)[np.argsort(angles)]

        # finish
        new_regions.append(new_region.tolist())

    return new_regions, np.asarray(new_vertices)

def fig_to_numpy(fig, alpha=1) -> np.ndarray:
    '''
    Converts matplotlib figure to a numpy array. 
    
    Source 
    ------
    Adapted from https://stackoverflow.com/questions/7821518/matplotlib-save-plot-to-numpy-array
    '''
    
    # Setup figure 
    fig.patch.set_alpha(alpha)    
    fig.canvas.draw()

    # Now we can save it to a numpy array.
    data = np.fromstring(fig.canvas.tostring_rgb(), dtype=np.uint8, sep='')
    data = data.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    
    return data

def voronoi_atoms(bs,cmap, bs_out=None,size=None, alpha=0.5, projection=lambda a,b: a/abs(b)):

    pd.options.mode.chained_assignment = None
    
    # read molecules in mol2 format 
    atoms = PandasMol2().read_mol2(bs)
    pt = atoms.df[['subst_name','atom_type', 'atom_name','x','y','z']]
    
    # convert 3D  to 2D 
    pt["P(x)"] = pt[['x','y','z']].apply(lambda coord: projection(coord.x,coord.z), axis=1) 
    pt["P(y)"] = pt[['x','y','z']].apply(lambda coord: projection(coord.y,coord.z), axis=1)  

    
    # setting output image size, labels off, set 120 dpi w x h
    size = 120 if size is None else size
    figure = plt.figure(figsize=(2.69 , 2.70),dpi=int(size))
    ax = plt.subplot(111); ax.axis('off') ;ax.tick_params(axis='both', bottom='off', left='off',right='off',labelleft='off', labeltop='off',labelright='off', labelbottom='off')

    # compute Voronoi tesselation
    vor = Voronoi(pt[['P(x)','P(y)']])
    regions, vertices = voronoi_finite_polygons_2d(vor)
    polygons = []
    for i in regions:
        polygon = vertices[i]
        polygons.append(polygon)
    pt.loc[:,'polygons'] = polygons
    
    # Compute Voronoi tesselation
    vor = Voronoi(atoms[['P(x)','P(y)']])
    regions, vertices = voronoi_finite_polygons_2d(vor)
    polygons = []
    for reg in regions:
        polygon = vertices[reg]
        polygons.append(polygon)
    atoms.loc[:,'polygons'] = polygons
        
    # Check alpha
    alpha=float(alpha)
        
    for i, row in atoms.iterrows():
        atom_type = atoms.loc[i][['atom_type']][0]
        colored_cell = matplotlib.patches.Polygon(row["polygons"],  
                                        facecolor = cmap[atom_type]["color"], 
                                        edgecolor = 'black',
                                        alpha = alpha  )
        ax.add_patch(colored_cell)
     
    ax.set_xlim(vor.min_bound[0] , vor.max_bound[0])
    ax.set_ylim(vor.min_bound[1] , vor.max_bound[1])
    
    # output image saving in any format; default jpg
    bs_out = 'out.jpg' if bs_out is None else bs_out
    plt.savefig(bs_out, frameon=False,bbox_inches="tight", pad_inches=False)
    return None

def myargs():
    parser = argparse.ArgumentParser('python')                                              
    parser.add_argument('-mol', required = True, help = 
                        'location of the protein/ligand mol2 file path')
    parser.add_argument('-out', required = False, help = 'location for the image to be saved')
    parser.add_argument('-dpi', required = False, help = 'image quality in dpi, eg: 300')
    parser.add_argument('-alpha', required = False, help = 'alpha for color of cells')

    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = getArgs()
    
    # Check for color mapping file, make dict 
    try:
        with open("./labels_mol2.csv") as cMapF:
            
            # Parse color map file 
            cmap  = np.array([line.replace("\n","").split("; ") for line in cMapF.readlines() if not line.startswith("#")])
            # To dict
            cmap = {atom:{"color":color, "definition":definition} for atom, definition, color in cmap}     
    except FileNotFoundError:
        raise FileNotFoundError("Color mapping file not found in directory")
 
    # Run 
    voronoi_atoms(args.mol,cmap, bs_out=args.out,size=args.dpi)
