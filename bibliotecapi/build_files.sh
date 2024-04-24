#!/bin/bash

# Update pip
echo "Updating pip..."
python3.9 pip install -U pip

# Install dependencies

echo "Installing project dependencies..."
python3.9 -m pip install -r requirements.txt

# Make migrations
echo "Making migrations..."
python3.9 manage.py makemigrations --noinput
python3.9 manage.py migrate --noinput

# Collect staticfiles
echo "Collect static..."
python3.9 manage.py collectstatic --noinput --clear

echo "Build process completed!"