# Pixy, an Ace Combat themed photo borderiser
# Imaging and plotting modules
from PIL import Image
from PIL.ExifTags import TAGS
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from math import log10
# System modules
import argparse
import sys
import io 
from pathlib import Path
# Progress bar
from tqdm import tqdm

FONT = "VT323.ttf"
  
def read_exif(image):
  """
  Read exif data, convert to dictionary, use EXIF data tags as keys
  """
  exif = {}
  for (k,v) in image._getexif().items():
    field = TAGS.get(k)
    exif[field] = v
  return exif

def get_film_speed(exif):
  iso = exif["ISOSpeedRatings"]
  iso_log = round(10 * log10(iso) + 1)
  iso_text = "{}/{}º".format(iso,iso_log)
  return iso_text

def get_shutter_speed(exif):
  """
  Get exposure time, return in a human readible format (1/500th etc)
  """
  ss = exif["ExposureTime"]
  if ss < 0.5:
    ss = int(1/ss)
    ss_text = "1/{}s".format(ss)
  else:
    ss_text = "{}s".format(ss)
  return ss_text

def get_aperture(exif):
  """
  Get aperture, return in a readible format
  """
  aperture = exif["FNumber"]
  aperture_text = "f/{:.2g}".format(float(aperture))
  return aperture_text

def patch_names(str):
  """
  This is a real fucking hack, I'm sorry
  I just don't like the way certain things present themselves in exif, usually too long
  """
  str = str.replace("OLYMPUS IMAGING CORP.","OLYMPUS")
  str = str.replace("iPhone 13 back camera 1.54mm f/2.4","Ultrawide Camera")
  str = str.replace("iPhone 13 back camera 5.1mm f/1.6","Wide Camera")
  str = str.replace("DC DN | C 016","")
  str = str.replace("LUMIX G VARIO","LUMIX G")
  return str

def main(args):
  print("<< Have you found your reason to fight yet? >>")
  # Iterate through list of filenames, use tqdm for progress bar
  filenames_prog = tqdm(args.filenames)
  for filename in filenames_prog:
    # Muck about with the filename
    filename_only = Path(filename).stem
    filenames_prog.set_description(filename_only)
    output_filename = "pixy-"+filename_only+".jpg"
    # Open the image! Extract the EXIF data!
    image = Image.open(filename)
    exif = read_exif(image)
    # If set to metadata mode, print the metadata
    if args.print_metadata:
      print("=== METADATA ===")
      print(type(exif))
      for key in exif.keys():
        val = exif[key]
        print("{} = {}".format(key,val))
      # return
    # Get strings for camera and lens make
    camera_make  = exif["Make"] + " " + exif["Model"]

    if args.manual_lens == True:
      print("Missing Lens data! Maybe using a manual lens?")
      lens_make = input("Lens model?\n> ")
      focal_length = input("Focal length?\n> ")
      exif["FNumber"] = input("Aperture?\n> ")
    elif "LensMake" in exif:
      lens_make    = exif["LensMake"] + " " + exif["LensModel"]
      focal_length = str(int(exif["FocalLength"])) + "mm"
    else:
      lens_make    = exif["LensModel"]
      focal_length = str(int(exif["FocalLength"])) + "mm"
    
    camera_make  = patch_names(camera_make)
    lens_make    = patch_names(lens_make)

    # lens_make   = exif["LensMake"] + " " + exif["LensModel"]
    # Get text for aperture section
    aper_text = get_aperture(exif)
    # Get text for shutter speed section
    ss_text = get_shutter_speed(exif)
    # Get text for ISO section
    iso_text = get_film_speed(exif)
    # Combine it all together, also lmao bottom text
    top_text = "{} & {}".format(camera_make,lens_make,ss_text,aper_text,iso_text)
    bottom_text    = "ISO {}, {}, {}@{}".format(iso_text,focal_length,ss_text,aper_text)
    # Resize image to fit within boundaries, use Lanczos resizing to preserve quality somewhat
    # Find size of image after resizing and bordering, this could be off by a pixel or two
    longest_axis = max(image.size) # Longest image axes, x for landscape, y for portrait
    scale = args.resolution / longest_axis # Find 
    x_resize = int(image.size[0] * scale)
    y_resize = int(image.size[1] * scale)
    # Resize the image
    img_resize = image.resize((x_resize,y_resize),resample=Image.Resampling.LANCZOS)
    # Make a new canvas for the final image
    canvas = Image.new("RGB",(args.canvas_size,args.canvas_size))
    # Overlay resized image
    offset = ((canvas.size[0] - img_resize.size[0]) // 2, (canvas.size[1] - img_resize.size[1]) // 2)
    canvas.paste(img_resize,offset)
    # Off piste horrible stuff, we're now using matplotlib to render the text
    # This is because matplotlib is a very good hammer, and this looks awfully like a nail
    fig = plt.figure(frameon=False)
    fig.set_size_inches(args.canvas_size/1000.,args.canvas_size/1000.)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(canvas)
    # Grab font from folder
    prop = fm.FontProperties(fname=sys.path[0]+"/"+FONT)
    if args.no_metadata == False:
      # plt.text(min(offset),offset[1],"■■■■■■■",c="#FAA43D",va="bottom",fontproperties=prop)
      plt.text(offset[0],offset[1],top_text,c="#FAA43D",va="bottom",fontproperties=prop)
      plt.text(offset[0],args.canvas_size-offset[1]+10,bottom_text,c="#FAA43D",va="top",fontproperties=prop)

      if args.attribution != "":
        plt.text(offset[0],args.canvas_size/2,args.attribution,c="#FAA43D",va="center",ha="right",fontproperties=prop,rotation=90)
        # plt.text(args.canvas_size-offset[0],args.canvas_size/2,args.attribution,c="#FAA43D",va="center",ha="left",fontproperties=prop,rotation=270)


    # Now that image is rendered, save to memory, store as tif to avoid generational loss
    buffer = io.BytesIO()
    plt.savefig(buffer,dpi=1000,format="tif")
    buffer.seek(0)
    # Optimise, bring down to filesize limit as defined by args.max_filesize
    opt_img = Image.open(buffer)
    opt_img = opt_img.convert('RGB')
    optimised = False
    q = 100
    while optimised == False:
      opt_buffer = io.BytesIO()
      opt_img.save(opt_buffer,format="JPEG",quality=q,optimize=True)
      opt_buffer.seek(0)
      filesize = sys.getsizeof(opt_buffer)
      if filesize < args.max_filesize * 1e6:
        # I know megabytes vs mebibytes etc. but I'm tired
        optimised = True
        with open(output_filename, "wb") as f:
          f.write(opt_buffer.getbuffer())
      q -= 1
  # Done!
  print("<< Thanks friend, see you again. >>")

if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    prog="Pixy v1.0 \"Solo Wing\"",
    description="<< Yo buddy... Still aasdlive? >>",
    epilog="<< Thanks friend, see you again.\nCode by Atomsite, GLWTPL 2024 >>"
  )
  parser.add_argument("filenames",
                      nargs='+',
                      help="Filenames of images to convert")
  parser.add_argument("-a","--attribution",
                      type=str,
                      default="",
                      help="Attribution")
  parser.add_argument("-m","--manual_lens",
                      action="store_true",
                      help="Image using a manual lens, prompts for lens information instead of fetching automatically")
  parser.add_argument("-r","--resolution",
                      type=int,
                      help="Largest axis resolution, default 3840px",
                      default=3840)
  parser.add_argument("-c","--canvas_size",
                      type=int,
                      help="Canvas size, default 4096px",
                      default=4096)
  parser.add_argument("-s","--square",
                      action="store_true",
                      help="Use a square image, ignore image resolution")
  parser.add_argument("-meta","--print_metadata",
                      action="store_true",
                      help="Instead of producing the image, instead print the image metadata")
  parser.add_argument("-M","--max_filesize",
                      type=float,
                      help="Maximum filesize, in Megabytes, of the output files, default is just under 5MB",
                      default=4.8)
  parser.add_argument("-nd","--no_metadata",
                      action="store_true",
                      help="Hide all metadata (removes text label at bottom of image)")
  args = parser.parse_args()
  main(args)