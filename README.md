# MedusaHC

OrcaSlicer post-processing plugin. After a tool change it puts the XY travel before a leading Z hop and carries the hop feedrate onto that travel. After the first layer change it turns later `M109` temperature waits into `M104` temperature sets.

OrcaSlicer 2.5 runs this from the slicing-pipeline picker. That is the post-processing step: the plugin edits the exported file and does not change the Slice preview on a non-Bambu printer.

## Install

1. In OrcaSlicer, open **Plugins** and choose **Install local plugin**.
2. Select `medusahc.py`.
3. Switch the process preset to Advanced mode.
4. Under **Process > Others > Slicing Pipeline Plugin**, select **MedusaHC**.
5. Under **Process > Others > Plugin Configuration**, open MedusaHC and set the two checkboxes. They are saved with that process preset.

Both checkboxes default to on. Turn off **Convert M109 to M104 after the first layer** when a preset should only swap the tool-change travel.

Remove the old machine-specific Python post-process script from the same preset. Leaving it in place rewrites the file twice.

## When it runs

On a non-Bambu printer the rewrite runs when you export G-code or use Print / Send. The Slice preview keeps the file from before this step. On a Bambu Lab printer it runs once during slicing, and the preview can show the result.

## Tests

From this directory:

```
python -m unittest tests.test_medusahc
```
