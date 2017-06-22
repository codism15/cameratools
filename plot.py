import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

X = 
ax.plot_wireframe(X, Y, Z, rstride=10, cstride=10)