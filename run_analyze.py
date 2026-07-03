#!/usr/bin/env python3
"""Wrapper to run stock analysis with proper __file__."""
import sys
sys.argv = ['stock_full_report_ths_integrated.py', '688099', '--mode', 'ths-enhanced']
exec(open('stock_full_report_ths_integrated.py').read())
