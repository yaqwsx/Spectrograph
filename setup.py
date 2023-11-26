from setuptools import setup, find_packages

setup(
    name="Spectrograph",
    version="0.1.0",
    description="Tool to measure vibrations",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Jan Mrázek",
    author_email="email@honzamrazek.cz",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "cobs~=1.2",
        "pyserial>=3.5",
        "PyQt5~=5.15",
        "pyqtgraph~=0.13",
        "scipy~=1.11"
    ],
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
    ],
)
