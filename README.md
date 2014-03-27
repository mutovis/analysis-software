batch-iv-analysis
=================

GUI python program to do batch curve fitting on data files generated by the McGehee LabVIEW IV measurement tool. The algorithm here attempts to fit IV data points to the characteristic equation of a solar cell:  

![Equation](http://upload.wikimedia.org/math/4/7/d/47d17d3c2fe8840d0b3181860bd22f0a.png)


### How to use
---
- Start the program with `python batch-iv-analysis.py` if you have python and all of the required packages installed
 - If you're running windows and you don't have python installed, you can try running batch-iv-analysis.exe from a release package
- Open the files for analysis with File --> Open (can select multiple files here) 

### Features
---
- Double click anywhere in the table to bring up a graph to compare the fitted curve with the raw data for the data associated with the line you clicked (this is a good way to verify that the curve fit is good)
 - This feature seems to crash under windows if you do this without closing a previously opened graph window
- Hover over the file name in each column to see the LabVIEW generated summary data for that file (for comparison purposes)

### Files contained here
---
- **batch-iv-analysis.py**
 - Main python script. Run this to use the tool. You can edit the code in this file directly using your favorite editor.
- **batch-iv-analysis.ui**
 - Contains user interface design, edit with Qt Designer (I used version 4.8.5)
- **batch_iv_analysis_UI.py**
 - Do not edit this file directly. Instead generate it from batch-iv-analysis.ui by issuing `pyuic4 batch-iv-analysis.ui > batch_iv_analysis_UI.py`
- **setup.py**
 - Use this file to generate standalone release packages (see instructions below)

### How to generate a standalone release package (for windows/OSX)
---
To generate an install package for a specific platform (windows or OSX) you must do these steps on that platform. This has only been tested under windows but should also work for macs. There is no need to generate a release package for Linux, just run the script directly.
- Install python and all the packages this project depends on
 - Make sure you can run the program directly with `python batch-iv-analysis.py` before proceeding
- Install cx_freeze
- run `python setup.py build`
- The standalone release files will be in a newly created folder called build
 - These files can then be copied to another computer to run the tool there
- It's also possible to generate installers with setup.py see the cx_Freeze docs for more info

### Python packages required
---
I can't remember
