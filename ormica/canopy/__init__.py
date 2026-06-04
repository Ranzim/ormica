"""
canopy — permission and root control.

Before any agent spawns a sub-agent, the request rises up the tree
to the appropriate authority — sometimes the parent, sometimes the
root owner. canopy assesses risk and routes approval, preventing
uncontrolled agent growth.

Biological metaphor: the forest canopy that controls light and growth below.
"""
