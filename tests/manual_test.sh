#!/bin/bash
# Basic functionality test for Colorado Legislature Monitor

cd ~/.claude/skills/colorado-legislature

echo "Testing Colorado Legislature Monitor"
echo "====================================="
echo ""

# Test basic commands to verify functionality
echo "1. Version check..."
python3 scripts/legislature.py version

echo ""
echo "2. JBC Schedule..."
python3 scripts/legislature.py jbc schedule --week current | head -20

echo ""
echo "3. List committees..."
python3 scripts/legislature.py committees | head -20

echo ""
echo "4. List bills..."
python3 scripts/legislature.py bills list --limit 3

echo ""
echo "5. Search..."
python3 scripts/legislature.py search housing | head -15

echo ""
echo "====================================="
echo "Basic functionality test complete"
