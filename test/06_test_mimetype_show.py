


image_name = "xxx.png"

video_name = "xxx.mp4"

from mimetypes import guess_type

print(guess_type(image_name)[0])
print(guess_type(video_name)[0])