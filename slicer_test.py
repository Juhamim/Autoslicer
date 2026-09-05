import slicer
with open('slicer_test_out.txt', 'w') as f:
    f.write('OK ' + slicer.app.applicationVersion)
slicer.app.exit(0)
