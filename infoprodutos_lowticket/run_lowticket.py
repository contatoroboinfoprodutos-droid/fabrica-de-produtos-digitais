"""Execução independente: python -m infoprodutos_lowticket.run_lowticket --slot manha"""
import argparse
from .crew import run_lowticket

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--slot", choices=["manha", "tarde"], required=True)
    print(run_lowticket(p.parse_args().slot))
