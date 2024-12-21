# Create a virtual environment named 'venv'
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "Failed to create virtual environment"
    exit 1
fi

# Activate the virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment"
    exit 1
fi

echo "Virtual environment 'venv' created and activated."