import setuptools

about = {}
with open("landroidcc/_about_.py") as fp:
    exec(fp.read(), about)

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="landroidcc",
    version=about["__version__"],
    author="Alexander Weggerle",
    author_email="alexander@weggerle.de",
    description="Accessing landroid mowers through the cloud",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    install_requires=[
       'pyOpenSSL', 'requests', 'paho-mqtt'
    ],
    entry_points={
        'console_scripts': ['landroidcc=landroidcc.cmdclient:main'],
    },
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
    ],
)