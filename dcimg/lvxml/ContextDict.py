from __future__ import absolute_import
from __future__ import print_function

from collections import MutableMapping
from itertools import chain
import itertools
try:
    imap = itertools.imap
except:
    imap = map

"""Nested contexts trees for implementing nested scopes (static or dynamic)

Based on http://code.activestate.com/recipes/577434/ (r2)
"""

class ContextDict(MutableMapping):
    ''' Nested contexts -- a chain of mapping objects.
    
    NOTE - I modified this so that newchild doesn't add the newchild to the list
            I also added something that allows you to 'adopt' dictionaries

    c = Context()           Create root context
    d = c.new_child()       Create nested child context. Inherit enable_nonlocal
    e = c.new_child()       Child of c, independent from d
    e.root                  Root context -- like Python's globals()
    e.map                   Current context dictionary -- like Python's locals()
    e.parent                Enclosing context chain -- like Python's nonlocals

    d['x']                  Get first key in the chain of contexts
    d['x'] = 1              Set value in current context
    del['x']                Delete from current context
    list(d)                 All nested values
    k in d                  Check all nested values
    len(d)                  Number of nested values
    d.items()               All nested items

    Mutations (such as sets and deletes) are restricted to the current context
    when "enable_nonlocal" is set to False (the default).  So c[k]=v will always
    write to self.map, the current context.

    But with "enable_nonlocal" set to True, variable in the enclosing contexts
    can be mutated.  For example, to implement writeable scopes for nonlocals:

        nonlocals = c.parent.new_child(enable_nonlocal=True)
        nonlocals['y'] = 10     # overwrite existing entry in a nested scope

    To emulate Python's globals(), read and write from the the root context:

        globals = c.root        # look-up the outermost enclosing context
        globals['x'] = 10       # assign directly to that context

    To implement dynamic scoping (where functions can read their caller's
    namespace), pass child contexts as an argument in a function call:

        def f(ctx):
            ctx.update(x=3, y=5)
            g(ctx.new_child())

        def g(ctx):
            ctx['z'] = 8                    # write to local context
            print ctx['x'] * 10 + ctx['y']  # read from the caller's context

    '''
    def __init__(self, enable_nonlocal=False, parent=None, parentkey=None):
        'Create a new root context'
        self.parent = parent 
        self.parentkey = parentkey
        self.enable_nonlocal = enable_nonlocal
        self.map = {}
        self.maps = [self.map]
#        if parent is not None:
#            self.maps += parent.maps

    def new_child(self, key,  enable_nonlocal=None):
        'Make a child context, inheriting enable_nonlocal unless specified'
        enable_nonlocal = self.enable_nonlocal if enable_nonlocal is None else enable_nonlocal
        local_new_child = self.__class__(enable_nonlocal=enable_nonlocal, parent=self, parentkey=key)
        
        self.__setitem__(key, local_new_child )
        
        return local_new_child


    def new_child_adopt(self, key, input_adopted_child ,enable_nonlocal=None):
        'Make a child context, inheriting enable_nonlocal unless specified'
        enable_nonlocal = self.enable_nonlocal if enable_nonlocal is None else enable_nonlocal
        
        #local_new_child = self.__class__(enable_nonlocal=enable_nonlocal, parent=self)
        self.__setitem__(key,input_adopted_child)
        input_adopted_child.parent      = self
        input_adopted_child.parentkey   = key 
        
        return input_adopted_child

    def find_key_refs(self, key, sublevels = False):
        # returns list of references to all dictionarys with the key present (** doesn't return the actual value - but easily found)
 
        keylist = list() 
        #print str(self.map)
        for m in self.map: 
            if key in m:
                keylist.append(self)            
                
            #print str(m)
            if sublevels :
                try :
                    keylist.extend(self.map[m].find_key_refs(key, sublevels))
                except AttributeError:
                    pass                    
            

                  
        return keylist
        
   
    def find_key_value(self, key, sublevels = False):
        # returns first found key value
        keyvalue = None
        keyrefs = self.find_key_refs(key , sublevels)
     
        if len(keyrefs) > 1 : 
            raise Exception("Warning - more than one reference")
        
            
        keyvalue = keyrefs[0][key]                
 

        return keyvalue   
        
     
    def return_path_to_root(self,path_to_root = ""):
        # returns first found key value
        'Return root context (highest level ancestor)'
 
         
        return (path_to_root if self.parent is None else str().join([self.parent.return_path_to_root(), "['", self.parentkey,"']", path_to_root]))
               
        
    @property
    def root(self):
        'Return root context (highest level ancestor)'
        return self if self.parent is None else self.parent.root

    def __getitem__(self, key):
        for m in self.maps:
            if key in m:
                break
        return m[key]

    def __setitem__(self, key, value):
        if self.enable_nonlocal:
            for m in self.maps:
                if key in m:
                    m[key] = value
                    return
        self.map[key] = value

    def __delitem__(self, key):
        if self.enable_nonlocal:
            for m in self.maps:
                if key in m:
                    del m[key]
                    return
        del self.map[key]

    def __len__(self, len=len, sum=sum, imap=imap):
        return sum(imap(len, self.maps))

    def __iter__(self, chain_from_iterable=chain.from_iterable):
        return chain_from_iterable(self.maps)

    def __contains__(self, key, any=any):
        return any(key in m for m in self.maps)

    def __repr__(self, repr=repr):
        return ' -> '.join(imap(repr, self.maps))


    def __str__(self):
        return str(self.map).replace("{","\n{\n").replace( ",",",\n").replace( "}",",\n}")


if __name__ == '__main__':
    
    
    
    
    
    
    cdic = ContextDict()
    cdic['a'] = 1
    cdic['b'] = 2
    cdic2 = cdic.new_child('d')
    cdic2['c'] = 3
    print("cdic:\t\t",cdic)
    print("cdic['d']:\t", cdic2)
    assert repr(cdic) == "{'a': 1, 'b': 2, 'd': {'c': 3}}"







    cdic3 = cdic2.new_child('e')
    cdic3['d'] = 4
    cdic3['b'] = 5
    print("cdic:\t\t",cdic)    
    print('cdic3:\t\t', cdic3)
    #assert repr(e) == "{'b': 5, 'd': 4} -> {'c': 3} -> {'a': 1, 'b': 2}"

    cdic4 = cdic2.new_child('f',enable_nonlocal=True)
    cdic4['d'] = 4
    cdic4['b'] = 5
    print("cdic:\t\t",cdic)    
    print('cdic4:\t\t', cdic4)
    #assert repr(f) == "{'d': 4} -> {'c': 3} -> {'a': 1, 'b': 5}"

    print(len(cdic4))
    #assert len(f) == 4
    #assert len(list(f)) == 4
    #assert all(k in f for k in f)
    #assert f.root == c
    
    # Test finding things throught the dictionary chain.
    print("cdic.find_key_refs('b') : \t" ,str(cdic.find_key_refs('b')))
    print("cdic.find_key_refs('b', True) : \t", str(cdic.find_key_refs('b', True)  ))

    print("cdic.find_key_refs('c', False) : \t" , str(cdic.find_key_refs('c', False)   ))
    
    print("cdic.find_key_refs('c', True) : \t" , str(cdic.find_key_refs('c', True)  )) 
 
    
    # Test adoption
    
    cdic_adopt = ContextDict()
    cdic_adopt['c'] = 99

    cdic.new_child_adopt('M',cdic_adopt)
    
    print("cdic  : ",cdic)
    print("cdic_adopt.root : ", cdic_adopt.root)
    
    
    print(cdic_adopt.return_path_to_root())
    
    
    print("cdic.find_key_refs('c', True) : \t" , str(cdic.find_key_refs('c', True)  )) 
    print("cdic.find_key_value('c', True) : \t" , str(cdic.find_key_value('c', True)  )) 
 
       
    
#    print cdic4.items()
#    print cdic4['d']
#    # dynanmic scoping example
#    def f(ctx):
#        print ctx['a'], 'f:  reading "a" from the global context'
#        print 'f: setting "a" in the global context'
#        ctx['a'] *= 999
#        print 'f: reading "b" from globals and setting "c" in locals'
#        ctx['c'] = ctx['b'] * 50
#        print 'f: ', ctx
#        g(ctx.new_child())
#        print 'f: ', ctx
#
#
#    def g(ctx):
#        print 'g: setting "d" in the local context'
#        ctx['d'] = 44
#        print '''g: setting "c" in f's context'''
#        ctx['c'] = -1
#        print 'g: ', ctx
#    global_context = Context(enable_nonlocal=True)
#    global_context.update(a=10, b=20)
#    f(global_context.new_child())
# end of http://code.activestate.com/recipes/577434/ }}}






 