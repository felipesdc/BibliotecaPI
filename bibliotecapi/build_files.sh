#!/bin/bash

# Update pip
echo "Updating pip..."
python3.12 pip install -U pip

# Install dependencies

echo "Installing project dependencies..."
python3.12 -m pip install -r requirements.txt

# Make migrations
echo "Making migrations..."
python3.12 manage.py makemigrations --noinput
python3.12 manage.py migrate --noinput

# Collect staticfiles
echo "Collect static..."
python3.12 manage.py collectstatic --noinput --clear

echo "Build process completed!"