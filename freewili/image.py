"""Module to create a FreeWili image file."""

import pathlib
import struct

from PIL import Image
from result import Err, Ok, Result


def convert(input_file: pathlib.Path, output_file: pathlib.Path) -> Result[str, str]:
    """Convert a PNG or JPEG image to a FreeWili image file (fwi extension).

    Parameters:
    ----------
    input_file : pathlib.Path:
        Path to the input image file (PNG or JPEG).

    output_file : pathlib.Path:
        Path to the output image file (.fwi).

    Returns:
    -------
        Result[str, str]:
            Ok(str) if the command was sent successfully, Err(str) if not.
    """
    try:
        im = Image.open(input_file)
        # print ("/* Image Width:%d Height:%d */" % (im.size[0], im.size[1]))
    except Exception as ex:
        return Err(f"Fail to open png or jpg file {input_file}: {ex}")

    image_height = im.size[1]
    image_width = im.size[0]

    try:
        outfile = open(output_file, "wb")
    except Exception as ex:
        return Err(f"Can't write the file {output_file}: {ex}")

    # HEADER section of FreeWili image (fwi extension)

    headerid = bytearray(bytes("FW01IMG\0", "ascii"))
    outfile.write(headerid)

    print(headerid)

    flags = struct.pack("<I", 1)  # Flags (1=transparent) unsigned int		iImageFlags;
    outfile.write(flags)

    totalpixelcount = struct.pack("<I", im.size[0] * im.size[1])  #  unsigned int		iImageTotalPixelCount;
    outfile.write(totalpixelcount)

    widthbytes = struct.pack("<h", im.size[0])  # unsigned short	iImageWidth;
    outfile.write(widthbytes)

    heightbytes = struct.pack("<h", im.size[1])  # unsigned short	iImageHeight;
    outfile.write(heightbytes)

    imagetransparentcolor = struct.pack("<h", 0)  # unsigned short	iImageTransparentColor; // always 0
    outfile.write(imagetransparentcolor)

    image_id = struct.pack("<h", 0)  # unsigned short	image_id; // always 0
    outfile.write(image_id)

    # do the acutal pixel bytes

    # for each pixel
    pix = im.load()

    hastransparency = False
    if len(pix[0, 0]) == 4:
        hastransparency = True

    for h in range(image_height):
        for w in range(image_width):
            # alternative conversion method
            # R=pix[w,h][0]>>3
            # G=pix[w,h][1]>>2
            # B=pix[w,h][2]>>3

            r = pix[w, h][0] / 255.0 * 31.0
            g = pix[w, h][1] / 255.0 * 63.0
            b = pix[w, h][2] / 255.0 * 31.0

            if hastransparency:
                if pix[w, h][3] == 0:  # transparent
                    rgb = 0  # transparent color
                else:
                    rgb = (int(r) << 11) | (int(g) << 5) | int(b)
            else:
                rgb = (int(r) << 11) | (int(g) << 5) | int(b)

            # swap
            rgb = ((rgb << 8) & 0xFF00) | ((rgb >> 8) & 0xFF)

            outfile.write(struct.pack("<H", rgb))

    outfile.close()

    return Ok(f"""png or JPG file "{input_file}" converted to FreeWili image file "{output_file}""")
