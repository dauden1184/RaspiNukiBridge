import asyncio

import re
from bleak import BleakScanner

START_GREEDY = range(1, 10)
ONE_SHOT = [10, ]


async def _device_mac_address(regex, logger, only_one):
    results = []
    if only_one:
        attempts = START_GREEDY
    else:
        attempts = ONE_SHOT

    for i in attempts:
        logger.debug(f'Scanning for {regex}')
        async with BleakScanner() as scanner:
            await asyncio.sleep(1.2 ** i)
        for d in scanner.discovered_devices:
            if re.match(regex, d.name):
                results.append(d)
        if results:
            logger.debug(f'Found {", ".join([r.name for r in results])}')
            return results


def find_ble_device(regex, logger, only_one=True):
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(_device_mac_address(regex, logger, only_one))
    loop.close()
    return result
