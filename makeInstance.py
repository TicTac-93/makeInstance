# ----------------------
#   Make Instance v1.0
# ----------------------

# Destroys instances of the dialog before recreating it
# This has to go first, before modules are reloaded or the ui_ var is re-declared.
try:
    ui_makeInstance.close()
except:
    pass

# --------------------
#       Modules
# --------------------

# PySide 2
from PySide2.QtUiTools import QUiLoader
import PySide2.QtWidgets as QtW
from PySide2.QtCore import QFile

# Import PyMXS, MaxPlus, and set up shorthand vars
import pymxs
import MaxPlus

maxscript = MaxPlus.Core.EvalMAXScript

# Misc
import os
import traceback


# --------------------
#      UI Class
# --------------------


class makeInstanceUI(QtW.QDialog):

    def __init__(self, ui_file, pymxs, parent=MaxPlus.GetQMaxMainWindow()):
        """
        The Initialization of the main UI class
        :param ui_file: The path to the .UI file from QDesigner
        :param pymxs: The pymxs library
        :param parent: The main Max Window
        """
        # Init QtW.QDialog
        super(makeInstanceUI, self).__init__(parent)

        # ---------------------------------------------------
        #                    Variables
        # ---------------------------------------------------

        self._ui_file_string = ui_file
        self._pymxs = pymxs
        self._parent = parent
        self._rt = pymxs.runtime

        # ---------------------------------------------------
        #                     Main Init
        # ---------------------------------------------------

        # UI Loader

        ui_file = QFile(self._ui_file_string)
        ui_file.open(QFile.ReadOnly)

        loader = QUiLoader()
        self._widget = loader.load(ui_file)

        ui_file.close()

        # Attaches loaded UI to the dialog box

        main_layout = QtW.QVBoxLayout()
        main_layout.addWidget(self._widget)

        self.setLayout(main_layout)

        # Titling

        self.setWindowTitle('Convert to Instances')

        # ---------------------------------------------------
        #                   Widget Setup
        # ---------------------------------------------------

        self._btn_src_pick = self.findChild(QtW.QPushButton, 'btn_src_pick')
        self._btn_src_select = self.findChild(QtW.QPushButton, 'btn_src_select')
        self._btn_src_clear = self.findChild(QtW.QPushButton, 'btn_src_clear')
        self._le_src_obj = self.findChild(QtW.QLineEdit, 'le_src_obj')

        self._btn_tgt_add = self.findChild(QtW.QPushButton, 'btn_tgt_add')
        self._btn_tgt_remove = self.findChild(QtW.QPushButton, 'btn_tgt_remove')
        self._btn_tgt_clear = self.findChild(QtW.QPushButton, 'btn_tgt_clear')
        self._list_tgt_obj = self.findChild(QtW.QListWidget, 'list_tgt_obj')

        self._btn_instance = self.findChild(QtW.QPushButton, 'btn_instance')
        self._btn_reference = self.findChild(QtW.QPushButton, 'btn_reference')

        # ---------------------------------------------------
        #                Function Connections
        # ---------------------------------------------------
        self._btn_src_pick.clicked.connect(self._src_pick)
        self._btn_src_select.clicked.connect(self._src_select)
        self._btn_src_clear.clicked.connect(self._src_clear)

        self._btn_tgt_add.clicked.connect(self._tgt_add)
        self._btn_tgt_remove.clicked.connect(self._tgt_remove)
        self._btn_tgt_clear.clicked.connect(self._tgt_clear)

        self._btn_instance.clicked.connect(self._instance)
        self._btn_reference.clicked.connect(self._reference)

        # ---------------------------------------------------
        #                  Parameter Setup
        # ---------------------------------------------------

        # Source and Target objects
        self._source = None
        self._targets = []

        # Label color vars
        self._err = '<font color=#e82309>Error:</font>'
        self._wrn = '<font color=#f7bd0e>Warning:</font>'
        self._grn = '<font color=#3cc103>Status:</font>'

        # ---------------------------------------------------
        #                   End of Init

    # ---------------------------------------------------
    #                  Private Methods
    # ---------------------------------------------------

    def _src_pick(self):
        """
        Run 3ds Max pickObject to select an object from the viewport or outliner
        """
        selection = self._rt.pickObject(message='Pick an Object to isntance...', prompt='')
        if selection != None:
            self._le_src_obj.setText(selection.name)
            self._source = selection

    def _src_select(self):
        """
        If a Source Object has been specified, select it in the scene.
        """
        if self._source != None:
            self._rt.select(self._source)

    def _src_clear(self):
        """
        Clear Source Object selection
        """
        self._le_src_obj.setText('')
        self._source = None

    def _tgt_add(self):
        """
        If there are objects selected, add non-duplicates to the internal list of targets and the GUI list.
        """
        rt = self._rt

        selection = list(rt.getCurrentSelection())
        if len(selection) > 0:
            for obj in selection:
                if obj not in self._targets:
                    self._targets.append(obj)

                    item = QListWidgetMaxItem(obj)
                    self._list_tgt_obj.addItem(item)
                else:
                    continue

    def _tgt_remove(self):
        """
        Remove any items that are currently selected IN THE GUI from the internal list of targets, as well as the GUI
        """
        items = list(self._list_tgt_obj.selectedItems())

        if len(items) > 0:
            for item in items:
                try:
                    self._targets.remove(item.maxObject())
                    self._list_tgt_obj.takeItem(self._list_tgt_obj.row(item))
                    del(item)
                except ValueError:
                    print "ERROR: Convert to Instance tried to remove %s from its memory, but couldn't find it!" %item.name()

    def _tgt_clear(self):
        """
        Clear the list of targets, both internal and GUI
        """
        self._targets = []
        self._list_tgt_obj.clear()


    def _instance(self):
        """
        Calls self._convert(type='instance')
        """
        self._convert('instance')

    def _reference(self):
        """
        Calls self._convert(type='reference')
        """
        self._convert('reference')

    def _convert(self, type):
        """
        Convert all objects in the list of targets to isntances of the Source Object
        :param type: string argument, 'instance' or 'reference'.  Specifies what to convert targets into.
        """
        rt = self._rt

        with self._pymxs.undo(True, 'Convert to Instances'), self._pymxs.redraw(False):
            try:
                # Check if there is, in fact, a Source Object chosen
                if self._source is None:
                    print "ERROR: Select a Source Object to be instanced!"
                    return
                # And at least one Target Object
                elif len(self._targets) == 0:
                    print "ERROR: Select at least one Target Object to be converted!"
                    return

                else:
                    # Copy the list of targets, and remove the Source Object from it if it's there
                    source = self._source
                    targets = self._targets
                    if source in targets:
                        targets.remove(source)

                    # Make all targets unique to prevent accidental instancing (happens if they're already instances
                    # of something else), then make them instances or references of source
                    rt.instanceMgr.MakeObjectsUnique(targets, rt.name('individual'))
                    if type == 'instance':
                        rt.instanceReplace(targets, source)
                    elif type == 'reference':
                        rt.referenceReplace(targets, source)
                    else:
                        print "ERROR: makeInstance._convert passed invalid type!  This shouldn't be able to happen!!"
                        raise ValueError

                return

            except Exception:
                traceback.print_exc()

                return

        return


class QListWidgetMaxItem(QtW.QListWidgetItem):

    def __init__(self, obj=None, name=None):
        """
        Initialization of the custom QListWidgetItem, QListWidgetMaxItem.
        This subclass adds new properties name and obj, as well as getters and setters for them.
        :param name: The name of the 3ds Max object being referenced by this item.  If not specified, this is
                        derived from the Max Object.
        :param obj: A reference to the actual 3ds Max object
        """
        # Init QtW.QListWidgetItem
        super(QListWidgetMaxItem, self).__init__()

        # ---------------------------------------------------
        #                  Parameter Setup
        # ---------------------------------------------------
        self._name = None
        self._maxObject = None

        # ---------------------------------------------------
        #                    Check Args
        # ---------------------------------------------------
        if name is not None:
            self._name = name
        elif obj is not None:
            self._name = obj.name

        if obj is not None:
            self._maxObject = obj

        # Set item text to the object name
        self.setText(self._name)

        # ---------------------------------------------------
        #                    End of Init

    # ---------------------------------------------------
    #                 Getters / Setters
    # ---------------------------------------------------
    def name(self):
        return self._name

    def setName(self, name):
        self._name = name

    def maxObject(self):
        return self._maxObject

    def setMaxObject(self, obj):
        self._maxObject = obj


# --------------------
#    Dialog Setup
# --------------------

# Path to UI file
_uif = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__))) + "\\makeInstance.ui"
_app = MaxPlus.GetQMaxMainWindow()
ui_makeInstance = makeInstanceUI(_uif, pymxs, _app)

# Punch it
ui_makeInstance.show()

# DEBUG
# print "\rTest Version 19"
