"""Transfer Hiyori's keyform deformation onto Mugi without copying her coordinates.

Copying every source keyform position by index once put Mugi's meshes at Hiyori's
absolute canvas coordinates: floating hair, white holes in the head, a missing
mouth. Nothing in that step could have caught it, because "the numbers arrived"
was the only thing being checked.

This package treats a keyform as a *displacement from its own mesh's reference
form*, pushes that displacement through the transform that maps the source
mesh's base shape onto the target's, and adds it to the target's own base shape.
The reference form therefore reproduces the target's base geometry exactly, and
every other form is Mugi's shape deformed the way Hiyori's is, in Mugi's frame.

The planner is pure: manifests in, a plan document out. It never opens Cubism.
Applying a plan and looking at the result are separate gates; see WORKFLOW.md.
"""
