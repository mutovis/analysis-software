batch-iv-analysis
=================

This project is a GUI python program to do batch curve fitting on data files generated by the McGehee LabVIEW IV measurement tool. The algorithm here attempts to fit IV data points to the characteristic equation of a solar cell:  

![Equation](http://upload.wikimedia.org/math/4/7/d/47d17d3c2fe8840d0b3181860bd22f0a.png)

### If you find this code useful...
---
Please cite our work:  
[DOI: 10.1039/C4EE02465F](http://pubs.rsc.org/en/Content/ArticleLanding/2014/EE/C4EE02465F)  
and shoot me an email. grey [AT] christoforo [DOT] net

### How to use
---
- Start the program with `python batch-iv-analysis.py` if you have python and all of the required packages installed
 - If you're running windows and you don't have python installed, you can try running batch-iv-analysis.exe in the exe zip from [the latest release](https://github.com/spraycoater/batch-iv-analysis/releases/latest/) (note that I create a new release whenever I feel like it and so using a release package typically means you're not running the latest code)
- Open the files for analysis with File --> Open (can select multiple files here)
 - A working example of the format of an input file is exampleData.csv, you can open that file to check that everything is working properly. All non-data rows in a valid input file must be preceded with #

### Features
---
- Hover over the column headers for a little blurb on what that column contains
- Double click anywhere in the table to bring up a graph to compare the fitted curve with the raw data associated with the line you clicked (this is a way to quickly check if the fit is good or bad)
 - This feature seems to crash under windows if you do this without closing a previously opened graph window
- Hover over the file name in each column to see the LabVIEW generated summary data for that file (for comparison purposes)
- The numbers shown in the table for Pmax, Vmax, Voc, I/Jsc and FF are calculated from a spline fit to the data.
 - Hovering over these values will show those calculated from the fit to the characteristic solar cell equation 
 - Hovering over other numbers in the table will show +/- 95% confidence intervals for that value
- Can read and plot i,v vs time data files generated by i-v-vs-time-taker. Does no analysis on them currently (but could in the future).

### Files here
---
- **batch-iv-analysis.py**
 - Main python script. Run this to use the tool. You can edit the code in this file directly using your favorite editor.
- **batch-iv-analysis.ui**
 - Contains user interface design for main window, edit with Qt Designer (I used version 4.8.5)
- **batch_iv_analysis_UI.py**
 - Do not edit this file directly. Instead generate it from batch-iv-analysis.ui by issuing:  
`pyuic4 -o batch_iv_analysis_UI.py batch-iv-analysis.ui`
- **interpolate.py**
 - Borrowed [from here](http://pywafo.googlecode.com/svn/trunk/pywafo/src/wafo/interpolate.py) this is needed for SmoothingSpline
- **polynomial.py**
 - Borrowed [from here](http://pywafo.googlecode.com/svn/trunk/pywafo/src/wafo/polynomial.py) this is needed for SmoothingSpline
- **setup.py**
 - Use this file to generate standalone release packages (see instructions below)

### How to generate a standalone release package (for windows/OSX)
---
To generate an install package for a specific platform (windows or OSX) you must do these steps on that platform. This has only been tested under windows but should also work for macs. There is no need to generate a release package for Linux, just run the script directly.
- Install python and all the packages this project depends on
 - Make sure you can run the program directly with `python batch-iv-analysis.py` before proceeding
- Install cx_freeze
- run `python setup.py build`
 - If you see an issue with exec_py3...something you can safely delete this file to solve the problem
- The standalone release files will be in a newly created folder called build
 - These files can then be copied to another computer to run the tool there
- It's also possible to generate installers with `setup.py`, see the cx_Freeze docs for more info

### Python packages required
---
I can't remember. Here are some:
- mpmath.libmp  
- gmpy
- scipy
- sympy -- must be a recent version, should probably upgrade with pip

To install the requirements in Debian/Ubuntu you can try:  
```
sudo apt-get install python2.7 python-mpmath python-gmpy python-sympy python-pip python2.7 python-scipy
sudo pip install --upgrade sympy
```

To install the requirements in Arch Linux you can try:  
```
sudo pacman -S python2 python2-mpmath python2-gmpy2 python2-sympy python2-scipy
```
