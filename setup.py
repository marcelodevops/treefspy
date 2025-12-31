from setuptools import setup, find_packages

setup(
    name="treefs",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["treefs"],
    install_requires=["PyYAML"],
    entry_points={
        "console_scripts": [
            "treefs = treefs:main",
        ],
    },
    description="Filesystem generator/importer using tree, YAML, or JSON formats.",
)
