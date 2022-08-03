import sys
import opentimelineio as otio
from tkinter import filedialog as fd

from deepdiff import DeepDiff, grep
from rich import print

class DiffTimelines():
    
    def __init__(self):
        self.files = tuple()
        self.timelines = tuple()
        self.diff = DeepDiff
        
    def select_files(self):
        
        filetypes = (
            ('FCP 7 XML V5', '*.xml'),
            ('FCPXML 1.3 - 1.9 ', '*.fcpxml'),
        )
        
        self.files = fd.askopenfilenames(
            title="Please select two files...", 
            filetypes=filetypes,
            initialdir="/"
        )
        
        if len(self.files) > 2:
            print("Hey! Just two files, please.")
            return self.select_files()
        
        
        elif not self.files:
            print("No files selected, exiting...")
            sys.exit()
            
        
        return self.files

    def get_timelines(self):
        
        timeline_1 = otio.adapters.read_from_file(self.files[0])
        timeline_2 = otio.adapters.read_from_file(self.files[1])
        
        self.timelines = (timeline_1, timeline_2)
        
    def get_diff(self):
        
        self.diff = DeepDiff(
            self.timelines[0], 
            self.timelines[1],
            view='tree',
        )
        return self.diff

def print_parent(x):
    
    if x is None:
        return
    
    parent = x.up
    print(parent)
    print_parent(parent)
    
    
        
if __name__ == "__main__":
    
    # dt = DiffTimelines()
    # dt.select_files()
    # print(dt.files)
    # dt.get_timelines()
    
    
    
    tl = otio.adapters.read_from_file("test_file.xml")
    for seq_index, seq in enumerate(tl.tracks):
        
        # print(dir(each_seq))
        for item_index, item in enumerate(seq):
      
            # Clips
            if isinstance(item, otio.schema.Clip):
                print(f"Track :{seq_index + 1} - Clip :{item.name} - Child Ref :{item_index + 1}")
                                
                timeline_in = item.trimmed_range_in_parent().start_time
                timeline_out = item.trimmed_range_in_parent().end_time_exclusive()               
                
                source_in = item.source_range.start_time
                source_out = item.source_range.end_time_exclusive()
                
                print(f"In on timeline: {timeline_in.to_timecode()}")
                print(f"Out on timeline: {timeline_out.to_timecode()}")
                
                print(f"Source in: {source_in.to_timecode()}")
                print(f"Source out: {source_out.to_timecode()}")
                
            print()
                
                # for x in clip.effects:
                #     print(f"Effect: {x}")
                    
                # print(clip.metadata)
                

                
                # timecode_in = otio.opentime.to_timecode(t_range[0])
                # timecode_out = otio.opentime.to_timecode(t_range[1])
                # print(timecode_in, timecode_out)
                
                # print(clip.media_reference)
                
                # print(clip.metadata)
                
            # 
    
    
    
    
    # diff = dt.get_diff()
    
    # # drop
    # print(f"All changes:\n{diff}")
    
    # for k, v in diff.items():
    #     print(f"Type: {k}")
        
    #     for x in v:
    #         print_parent(x)
            
            

