import sys
import datetime
import math
import numpy as np
from astrodata import AstroData

def profile_numpy(data,xc,yc,bg,stamp_size=10):
    
    # Check that there's enough room for a stamp
    sz = stamp_size
    if (int(yc)-sz<0 or int(xc)-sz<0 or
        int(yc)+sz>=data.shape[0] or int(xc)+sz>=data.shape[1]):
        return (np.nan,np.nan)

    # Get image stamp around center point
    stamp=data[int(yc)-sz:int(yc)+sz,int(xc)-sz:int(xc)+sz]

    # Build the radial profile
    ctr_coord = np.mgrid[int(yc)-sz:int(yc)+sz,int(xc)-sz:int(xc)+sz] + 0.5
    dist = np.array([ctr_coord[0]-yc,ctr_coord[1]-xc])
    dist = np.sqrt(np.sum(dist**2,axis=0))
    rpr = dist.flatten()
    rpv = stamp.flatten() - bg
    
    # Sort by the radius
    sort_order = np.argsort(rpr)
    radial_profile = np.rec.fromarrays([rpr[sort_order],rpv[sort_order]],
                                       names=["radius","flux"])

    # Find the first point where the flux falls below half
    maxflux = np.max(radial_profile["flux"])
    halfflux = maxflux/2.0
    first_halfflux = np.where(radial_profile["flux"]<=halfflux)[0]
    if first_halfflux.size<=0:
        # Half flux not found, return the last radius
        hwhm = radial_profile["radius"][-1]
    else:
        hwhm = radial_profile["radius"][first_halfflux[0]]

    # Find the first radius that encircles half the total flux
    sumflux = np.cumsum(radial_profile["flux"])
    totalflux = sumflux[-1]
    halfflux = totalflux / 2.0
    first_50pflux = np.where(sumflux>=halfflux)[0]
    if first_50pflux.size<=0:
        ee50r = radial_profile["radius"][-1]
    else:
        ee50r = radial_profile["radius"][first_50pflux[0]]

    return (hwhm, ee50r)

def profile_loop(data,xc,yc,bg,sz):

    stamp=data[int(yc)-sz:int(yc)+sz,int(xc)-sz:int(xc)+sz]

    # Build the radial profile
    rpr=[]
    rpv=[]
    for y in range(int(yc)-sz, int(yc)+sz):
        for x in range(int(xc)-sz, int(xc)+sz):
            # Compute the distance of the center of this pixel 
            # from the centroid location
            dx = (float(x)+0.5) - xc
            dy = (float(y)+0.5) - yc
            d = math.sqrt(dx*dx + dy*dy)
            rpr.append(d)
            rpv.append(data[y, x])

    maxflux = np.max(rpv) - bg
    halfflux = maxflux/2.0

    sort = np.argsort(rpr)

    i=0
    flux=maxflux
    hwhm=0
    while (flux > halfflux and i<len(sort)):
      flux=rpv[sort[i]]-bg
      hwhm = rpr[sort[i]]
      i+=1

    # OK, now calculate the total flux
    bgsub = stamp - bg
    totalflux = np.sum(bgsub)

    # Now make the radial profile into a 2d numpy array
    rp = np.array([rpr, rpv], dtype=np.float32)
    sort = np.argsort(rp[0])

    halfflux = totalflux / 2.0

    # Now step out through the rp until we get half the flux
    flux=0
    i=0
    while (flux < halfflux):
      #print "adding in r=%.2f v=%.1f" % (rp[0][sort[i]], rp[1][sort[i]]-bg)
      flux+= rp[1][sort[i]]-bg
      i+=1

    # subtract 1 from the index -- 1 gets added after the right flux is found
    ee50r = rp[0][sort[i-1]]

    return (hwhm, ee50r)

filename = sys.argv[1]
ad = AstroData(filename)
objcat = ad['OBJCAT',1]
sci = ad['SCI',1]
catx = objcat.data.field("X_IMAGE")
caty = objcat.data.field("Y_IMAGE")
catfwhm = objcat.data.field("FWHM_IMAGE")
catbg = objcat.data.field("BACKGROUND")
data = sci.data

nobj = len(catx)
print "%d objects" % nobj

# the numpy way
print 'numpy'
now = datetime.datetime.now()
hwhm_list = []
e50r_list = []
for i in range(0,len(objcat.data)):
    xc = catx[i]
    yc = caty[i]
    bg = catbg[i]

    xc -= 0.5
    yc -= 0.5

    hwhm,e50r = profile_numpy(data,xc,yc,bg)
    #print i,hwhm,e50r
    hwhm_list.append(hwhm)
    e50r_list.append(e50r)
print "  mean HWHM %.2f" % np.mean(hwhm_list)
print "  mean E50R %.2f" % np.mean(e50r_list)
elap = datetime.datetime.now() - now
print "  %.2f s" % ((elap.seconds*10**6 + elap.microseconds)/10.**6)


# the loopy way
print 'loopy'
now = datetime.datetime.now()
hwhm_list = []
e50r_list = []
for i in range(0,len(objcat.data)):
    xc = catx[i]
    yc = caty[i]
    bg = catbg[i]

    xc -= 0.5
    yc -= 0.5

    sz=10
    if (int(yc)-sz<0 or int(xc)-sz<0 or
        int(yc)+sz>=data.shape[0] or int(xc)+sz>=data.shape[1]):
        continue

    hwhm,e50r = profile_loop(data,xc,yc,bg,sz)
    #print i,hwhm,e50r
    hwhm_list.append(hwhm)
    e50r_list.append(e50r)
print "  mean HWHM %.2f" % np.mean(hwhm_list)
print "  mean E50R %.2f" % np.mean(e50r_list)
elap = datetime.datetime.now() - now
print "  %.2f s" % ((elap.seconds*10**6 + elap.microseconds)/10.**6)
