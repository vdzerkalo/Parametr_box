#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

echo "Setting up Autonomous Box Generator Environment..."

if [ ! -f "./bin/micromamba" ]; then
    echo "Downloading portable package manager (micromamba)..."
    mkdir -p bin
    wget -qO- https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj --strip-components=1 -C bin/ bin/micromamba
fi

if [ ! -d "./env" ]; then
    echo "Creating fully isolated Python 3.10 environment..."
    ./bin/micromamba create -p ./env python=3.10 -c conda-forge -y
    
    echo "Installing required Python packages exclusively via pip..."
    ./env/bin/pip install PySide6 pyqtgraph PyOpenGL "numpy<2.0.0"
    ./env/bin/pip install cadquery==2.4.0
fi

echo "Ensuring additional dependencies are installed..."
./env/bin/pip install mapbox-earcut shapely

echo "Environment ready! Starting application..."
./env/bin/python main.py
