from setuptools import setup, Extension
import pybind11

ext_modules = [
    Extension(
        "hypertork_cpp",
        ["hypertork_cpp.cpp"],
        include_dirs=[pybind11.get_include()],
        language='c++'
    )
]

setup(
    name="hypertork_cpp",
    ext_modules=ext_modules,
)