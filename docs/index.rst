.. include:: references.txt

.. |dcimg| replace:: :mod:`dcimg`

.. toctree::
   :maxdepth: 2
   
Welcome to dcimg
================

|dcimg| is a Python module for reading Hamamatsu's DCIMG file format,
which is used to buffer data from MOSCAM to disk.

Most people will use the |Ddata| class, which provides fast access to the 
header information and image data.

.. automodapi:: dcimg
    :no-inheritance-diagram:
    :skip: floor
    :skip: log10
    :skip: CCD
    :skip: MCCD
    :skip: PowerOnOffError
    :skip: Rwin
    :skip: Time
    :skip: UendError
    :skip: Window
    :skip: Uhead
    :skip: UltracamError
    :skip: test

API
===

.. autoclass:: dcimg.Ddata   
.. autoclass:: dcimg.Dhead

