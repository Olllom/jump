#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

import versioneer
from setuptools import setup

with open('README.md') as readme_file:
    readme = readme_file.read()


setup(
    author="Andreas Krämer, Ruggero Turra",
    author_email='kraemer.research@gmail.com, ruggero.turra@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="Running remote jupyter notebooks in a local browser.",
    entry_points={
        'console_scripts': [
            'jump=jump.jump:main',
        ],
    },
    #install_requires=['click >= 6.0', 'plumbum >= 1.5'],
    license="MIT license",
    long_description=readme,
    include_package_data=True,
    keywords='jump',
    name='jump',
    packages=['jump'],
    #setup_requires=['pytest-runner', ],
    #test_suite='tests',
    #tests_require=['pytest', ],
    url='https://github.com/Olllom/jump',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    #zip_safe=False,
)
