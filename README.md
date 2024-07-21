<h2>File paths that need to be changed:</h2>

<h3>mainV2.py</h3>

File Path for Transformation Matrix:
Update the file path to point to the correct location of the transformation matrix:

    transformation_matrix = np.loadtxt(r"C:\path\to\your\transformation_matrix.txt")

<h3>calibrationV2.py</h3>

File Path for Transformation Matrix:
Ensure the path to the transformation matrix is correct. This path must be consistent with where your transformation matrix file is located.

    np.savetxt(r"C:\path\to\your\transformation_matrix.txt", transformation_matrix)

<h3>main_GUI.py</h3>

File Paths for Scripts:
Update the paths to point to the correct location of the calibration and main scripts:

    CALIBRATION_SCRIPT_PATH = r"C:\path\to\your\calibrationV2.py"
    MAIN_SCRIPT_PATH = r"C:\path\to\your\mainV2.py"


