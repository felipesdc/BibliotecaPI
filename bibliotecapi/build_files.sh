#!/bin/bash

# Update pip
echo "Updating pip..."
python pip install -U pip

# Install dependencies

echo "Installing project dependencies..."
python -m pip install -r requirements.txt

# Make migrations
echo "Making migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Collect staticfiles
echo "Collect static..."
python manage.py collectstatic --noinput --clear

echo "Build process completed!"