import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["os","scipy.integrate.lsoda","scipy.integrate.vode","scipy.sparse.linalg","scipy.special._ufuncs","scipy.sparse.csgraph","scipy.special","PyQt4.QtCore","PyQt4.QtGui","matplotlib.backends.backend_tkagg","matplotlib.backends.backend_qt4agg"], "excludes": ["tkinter"]}

# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(  name = "batch-iv-analysis",
        version = "1.9",
        description = "Batch curve fitting tool for data files generated by the McGehee LabVIEW IV curve taker",
        options = {"build_exe": build_exe_options},
        executables = [Executable("batch-iv-analysis.py", base=base,icon="icon.ico")])
