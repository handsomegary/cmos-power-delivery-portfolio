"""Stage a portfolio Spectre input in a fresh local run directory."""

import argparse
from pathlib import Path
import shutil


def stage(template, models, output, controller=None):
    template = template.resolve(strict=True)
    models = models.resolve(strict=True)
    if controller is not None:
        controller = controller.resolve(strict=True)

    deck = template.read_bytes()
    model_name = str(models).replace('\\', '/')
    if any(c in model_name for c in ('\r', '\n', '"')):
        raise ValueError('Model binding path cannot appear in a Spectre include')
    if deck.count(b'include "models.local.scs"') != 1:
        raise ValueError('Template must contain exactly one local model binding')
    needs_controller = b'ahdl_include "buck_control.va"' in deck
    if needs_controller != (controller is not None):
        raise ValueError('The Buck template requires --controller. The LDO template uses only --models.')
    if not models.is_file() or (controller is not None and not controller.is_file()):
        raise ValueError('Model binding and controller must be regular files')

    # Keep the model binding in its original directory so relative includes resolve there.
    deck = deck.replace(b'include "models.local.scs"', f'include "{model_name}"'.encode('utf-8'))
    output.mkdir(parents=True, exist_ok=False)
    (output / 'input.scs').write_bytes(deck)
    if controller is not None:
        shutil.copyfile(controller, output / 'buck_control.va')
    return output / 'input.scs'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('template', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--models', required=True, type=Path, help='Local Spectre binding file for an installed model set')
    parser.add_argument('--controller', type=Path, help='Authored Buck Verilog-A controller')
    args = parser.parse_args()
    print(stage(args.template, args.models, args.output, args.controller))
