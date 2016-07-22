#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    case "${TOXENV}" in
        py35)
            # Install Python 3.5 from source
            wget https://www.python.org/ftp/python/3.5.2/Python-3.5.2.tar.xz
            tar -xf Python-3.5.2.tar.xz
            cd Python-3.5.2
            ./configure
            make
            make install
            cd ..
            rm -rf Python-3.5.2
        ;;
        py34)
            # Install Python 3.4 from source
            wget https://www.python.org/ftp/python/3.4.3/Python-3.4.3.tar.xz
            tar -xf Python-3.4.3.tar.xz
            cd Python-3.4.3
            ./configure
            make
            make install
            cd ..
            rm -rf Python-3.4.3
        ;;
    esac
fi

pip3 install -r requirements-tests.txt
