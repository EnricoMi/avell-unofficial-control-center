"""
Copyright (c) 2019, Rodrigo Gomes.
Distributed under the terms of the MIT License.
The full license is in the file LICENSE, distributed with this software.
Created on May 22, 2019
@author: @rodgomesc
"""
import argparse
import textwrap
import sys
import os
import usb.core
import usb._lookup
from aucc.core.handler import Device, DeviceHandler
import time
from aucc.core.colors import (get_mono_color_vector,
                              get_h_alt_color_vector,
                              get_v_alt_color_vector,
                              _colors_available)


# Keyboard brightness has 4 variations 0x08,0x16,0x24,0x32
brightness_map = {
    1: 0x08,
    2: 0x16,
    3: 0x24,
    4: 0x32
}

programs = {
    "breathing":          0x02,
    "wave":               0x03,
    "random":             0x04,
    "reactive":           0x04,
    "rainbow":            0x05,
    "ripple":             0x06,
    "reactiveripple":     0x07,
    "marquee":            0x09,
    "fireworks":          0x11,
    "raindrop":           0x0A,
    "aurora":             0x0E,
    "reactiveaurora":     0x0E,
}

colours = {
    "r": 0x01, # red
    "o": 0x02, # orange
    "y": 0x03, # yellow
    "g": 0x04, # green
    "b": 0x05, # blue
    "t": 0x06, # teal
    "p": 0x07, # purple
}

import re
light_style_pattern = "^({})({})?$".format(
                            '|'.join(programs.keys()),
                            '|'.join(colours.keys())
                        )
def get_light_style_code(style, brightness=3, speed=0x05) :
    match = re.match(light_style_pattern, style)
    
    if not match:
        raise Exception("Error: Style {} not found".format(style))
    else:
        match = match.groups()

    program = match[0]
    program_code = programs[program]

    colour_code = colours[match[1]]  if match[1] else 0x08 # Default rainbow colour
    brightness_code =  brightness_map[brightness]
    program2 = 0x00

    if program == "rainbow":
        colour_code = 0x00

    elif program == "marquee":
        colour_code = 0x08

    elif program == "wave":
        colour_code = 0x00
        program2 = 0x01

    elif program in ["reactive", "reactiveaurora", "fireworks"]:
        program2 = 0x01

    return get_code(program_code, speed=speed, colour=colour_code, brightness=brightness_code, program2=program2)


def get_code( program, speed=0x05, brightness=0x24, colour=0x08, program2=0x00, save_changes=0x00 ):
    # Byte  Purpose     Notes
    # 0     ???         0x08 to issue commands?
    # 1     ???         0x02 to issue commands? Other values seem to cause failure. 0x01 appears to switch off lights
    # 2     Program     The 'effect' in use
    # 3     Speed       0x0?: 1,2,3,4,5,6,7,8,9,a (fastest to slowest)
    # 4     Brightness  0x08, 0x16, 0x24, 0x32
    # 5     Colour      0x0?: 1 red, 2 orange, 3 yellow, 4 green, 5 blue, 6 teal, 7 purple, 8 rainbow
    # 6     Program?    Required to be changed for some effects
    # 7     save changes (00 for no, 01 for yes)
    return ( 0x08, 0x02, program, speed, brightness, colour, program2, save_changes )


class ControlCenter:
    def __init__(self, vendor_products):
        self.vendor_products = vendor_products
        self.brightness = None

    def get_devices(self):
        def match(dev):
            return (dev.idVendor in self.vendor_products and
                    (self.vendor_products[dev.idVendor] is None or
                     dev.idProduct in self.vendor_products[dev.idVendor]))

        devices = list(usb.core.find(find_all=True, custom_match=match))
        # in linux interface is 1, in windows 0
        if not sys.platform.startswith('win'):
            for device in devices:
                if device.is_kernel_driver_active(1):
                    device.detach_kernel_driver(1)

        return devices


    def disable_keyboard(self, device):
        device.ctrl_write(0x08, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)

    def keyboard_style(self, device, style, brightness=3, speed=5):
        device.ctrl_write(*get_light_style_code(style, brightness, speed=speed))

    def adjust_brightness(self, device, brightness=None):
        if brightness:
            self.brightness = brightness
            device.ctrl_write(0x08, 0x02, 0x33, 0x00,
                            brightness_map[self.brightness], 0x00, 0x00, 0x00)
        else:
            self.adjust_brightness(device, 4)

    def color_scheme_setup(self, device, save_changes=0x01):
        '''
        options available: (0x00 for no, 0x01 for yes)
        purpose: write changes on chip to keep current color on reboot
        '''
        device.ctrl_write(0x12, 0x00, 0x00, 0x08, save_changes, 0x00, 0x00, 0x00)

    def mono_color_setup(self, device, color_scheme):

        if self.brightness:
            self.color_scheme_setup(device)
            color_vector = get_mono_color_vector(color_scheme)
            device.bulk_write(times=8, payload=color_vector)
        else:
            self.adjust_brightness(device)
            self.mono_color_setup(device, color_scheme)

    def h_alt_color_setup(self, device, color_scheme_a, color_scheme_b):

        if self.brightness:
            self.color_scheme_setup(device)
            color_vector = get_h_alt_color_vector(color_scheme_a, color_scheme_b)
            device.bulk_write(times=8, payload=color_vector)
        else:
            self.adjust_brightness(device)
            self.h_alt_color_setup(device, color_scheme_a, color_scheme_b)

    def v_alt_color_setup(self, device, color_scheme_a, color_scheme_b):

        if self.brightness:
            self.color_scheme_setup(device)
            color_vector = get_v_alt_color_vector(color_scheme_a, color_scheme_b)
            device.bulk_write(times=8, payload=color_vector)
        else:
            self.adjust_brightness(device)
            self.v_alt_color_setup(device, color_scheme_a, color_scheme_b)


def main():
    from elevate import elevate

    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''
            Colors available:
            [red|green|blue|teal|pink|purple|white|yellow|orange|olive|maroon|brown|gray|skyblue|navy|crimson|darkgreen|lightgreen|gold|violet] '''),
        formatter_class=argparse.RawDescriptionHelpFormatter)

    ops_parser = parser.add_mutually_exclusive_group(required=True)
    ops_parser.add_argument('-l', '--list-devices', action='store_true',
                        help='List all available devices. Use --vendor or --product to look for other vendors.')
    ops_parser.add_argument('-c', '--color',
                        help='Select a single color for all keys.')
    ops_parser.add_argument('-H', '--h-alt', metavar='COLOR', nargs=2,
                        help='Horizontal alternating colors')
    ops_parser.add_argument('-V', '--v-alt', metavar='COLOR', nargs=2,
                        help='Vertical alternating colors')
    ops_parser.add_argument('-s', '--style',
                        help='One of (rainbow, marquee, wave, raindrop, aurora, random, reactive, breathing, ripple, reactiveripple, reactiveaurora, fireworks). Additional single colors are available for the following styles: raindrop, aurora, random, reactive, breathing, ripple, reactiveripple, reactiveaurora and fireworks. These colors are: Red (r), Orange (o), Yellow (y), Green (g), Blue (b), Teal (t), Purple (p). Append those styles with the start letter of the color you would like (e.g. rippler = Ripple Red')
    ops_parser.add_argument('-d', '--disable', action='store_true',
                        help='Turn keyboard backlight off')

    parser.add_argument(
        '-v', '--vendor', help='Set vendor id (e.g. 1165 or 0x048d).', type=str)
    parser.add_argument(
        '-p', '--product', help='Set product id.', type=str)
    parser.add_argument(
        '-D', '--device', help='Select device (1, 2, ...). Use -l to list available devices.', type=int)
    parser.add_argument(
        '-b', '--brightness', help='Set brightness, 1 is minimum, 4 is maximum.', type=int, choices=range(1, 5))
    parser.add_argument('--speed', type=int, choices=range(1,11),
                        help='Set style speed. 1 is fastest. 10 is slowest')

    parsed = parser.parse_args()

    vendor_products = {}
    if parsed.vendor:
        # convert potentially hexadecimal into decimal int
        vendor = int(parsed.vendor, 0)
        if parsed.product:
            product = int(parsed.product, 0)
            vendor_products[vendor] = [product]
        else:
            vendor_products[vendor] = None
    else:
        if parsed.product:
            product = int(parsed.product, 0)
            vendor_products[0x048d] = [product]
        else:
            vendor_products = {0x048d: [0xce00, 0x600b, 0x7001]}

    control = ControlCenter(vendor_products)

    if not os.geteuid() == 0:
        elevate()

    devices = control.get_devices()

    if parsed.list_devices:
        for idx, device in enumerate(devices):
            print(f"[{idx+1}] device #{idx+1} vendor={device.idVendor}, product={device.idProduct}")
        return

    if parsed.device:
        if parsed.device < 1 or parsed.device-1 >= len(devices):
            print(f"Device #{parsed.device} does not exist, there are {len(devices)} devices.")
            sys.exit(1)
        else:
            device = devices[parsed.device-1]
    else:
        if len(devices) == 0:
            print("No device found")
            sys.exit(1)
        if len(devices) > 1:
            print("Found multiple devices, please use -d to select one and -l to list them")
            sys.exit(1)
        device = devices[0]

    device_handler = DeviceHandler(device)

    if parsed.disable:
        control.disable_keyboard(device_handler)
    else :
        if parsed.style:
            speed = parsed.speed if parsed.speed else 5
            if parsed.brightness :
                control.keyboard_style(device_handler, parsed.style, parsed.brightness, speed=speed)
            else :
                control.keyboard_style(device_handler, parsed.style, speed=speed)
        else :
            if parsed.brightness:
                control.adjust_brightness(device_handler, int(parsed.brightness))
            if parsed.color:
                control.mono_color_setup(device_handler, parsed.color)
            elif parsed.h_alt:
                control.h_alt_color_setup(device_handler, *parsed.h_alt)
            elif parsed.v_alt:
                control.v_alt_color_setup(device_handler, *parsed.v_alt)
            else :
                print("Invalid or absent command")


if __name__ == "__main__":
    main()
