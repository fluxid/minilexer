#!/bin/sh

WORKING_DIR="$(cd "${0%/*}" 2>/dev/null; dirname "$PWD"/"${0##*/}")"
cd ${WORKING_DIR}

export PYTHON_PATH="${PWD}/src:${PYTHON_PATH}"
nosetests --with-coverage3 --cover3-package=fxd.minilexer --doctest-tests --with-doctest tests
