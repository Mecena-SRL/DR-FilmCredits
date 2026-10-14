#!/bin/bash
# DR-FilmCredits - installazione con doppio clic (macOS)
cd "$(dirname "$0")/.."
python3 install/install.py
echo
echo "Fatto. Riavvia DaVinci Resolve: Workspace > Scripts > Utility > DR-FilmCredits"
read -n 1 -s -r -p "Premi un tasto per chiudere"
