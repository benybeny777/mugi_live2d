"""Sandboxed layer completion: extract from PSD, hand to Photoshop, import back.

The generative fill attempt that ran directly on the master PSD failed because
every layer in that document covers the whole canvas and carries a layer mask,
so Photoshop generated over all 2976x4175 px instead of the visible part. This
package never touches the master document. It bakes a layer's mask into a small
transparent PNG, records exactly which pixels may change, and refuses to accept
a returned image that changed anything else.
"""
