import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="mutovis-analysis",
    version="3.0.7",
    author="Grey Christoforo",
    author_email="grey@mutovis.com",
    description="Software for analyzing solar cell i-v curves",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mutovis/analysis-software",
    packages=setuptools.find_packages(),
    entry_points={
        'gui_scripts': ['mutovis-analysis = batch_iv_analysis.__main__:main', ],
        'console_scripts': ['mutovis-analysis-cli = batch_iv_analysis.__main__:main'], },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL-3.0",
        "Operating System :: OS Independent",
    ],
)
