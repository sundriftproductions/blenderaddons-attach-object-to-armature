#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#======================= END GPL LICENSE BLOCK ========================

from bpy.props import *
import bpy
import bmesh
import os
import sys
import math

# Version History
# 1.0.0 - 2022-07-08: Original version.
# 1.0.1 - 2022-08-07: Misc formatting cleanup before uploading to GitHub.

bl_info = {
    "name": "Attach Object to Armature",
    "author": "Jeff Boller",
    "version": (1, 0, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Properties > Rigging",
    "description": "This Blender add-on helps the user attach an object to an existing armature, rather than "\
                   "manually going through the convoluted process of making sure the object is in the same "\
                   "collection as the armature, applying all modifiers to the object (if applicable), "\
                   "apply all transforms, and transferring weights.",
    "wiki_url": "https://github.com/sundriftproductions/blenderaddons-attach-object-to-armature/wiki",
    "tracker_url": "https://github.com/sundriftproductions/blenderaddons-attach-object-to-armature/",
    "category": "3D View"}

def select_name(name = '', extend = True ):
    if extend == False:
        bpy.ops.object.select_all(action='DESELECT')
    ob = bpy.data.objects.get(name)
    ob.select_set(state=True)
    bpy.context.view_layer.objects.active = ob

def apply_modifiers(obj):
    ctx = bpy.context.copy()
    ctx['object'] = obj
    for _, m in enumerate(obj.modifiers):
        try:
            ctx['modifier'] = m
            bpy.ops.object.modifier_apply(ctx, modifier=m.name)
        except RuntimeError:
            print(f"Error applying {m.name} to {obj.name}, removing it instead.")
            obj.modifiers.remove(m)

    for m in obj.modifiers:
        obj.modifiers.remove(m)

def find_collection(context, item):
    collections = item.users_collection
    if len(collections) > 0:
        return collections[0]
    return context.scene.collection

class AttachObjectToArmaturePreferencesPanel(bpy.types.AddonPreferences):
    bl_idname = __module__
    object_name_to_attach_to_armature: bpy.props.StringProperty(name = '', default = '', description = 'The object that you want to attach to an existing armature')
    armature_name: bpy.props.StringProperty(name = '', default = '', description = 'The armature that the object should be attached to')
    existing_body_object_name: bpy.props.StringProperty(name = '', default = '', description = 'An existing body object that will be used for weight transforms. If no such body exists, leave this blank.')
    apply_all_modifiers: bpy.props.BoolProperty(name='Apply all modifiers on this object', default=False, description='Apply all modifiers on this object')

class ATTACHOBJECTTOARMATURE_PT_Apply(bpy.types.Operator):
    bl_idname = "aota.attach_to_armature"
    bl_label = ""
    bl_options = {"REGISTER", "UNDO"}  # Required for when we do a bpy.ops.ed.undo_push(), otherwise Blender will crash when you try to undo the action in this class.

    def execute(self, context):
        bpy.ops.ed.undo_push()  # Manually record that when we do an undo, we want to go back to this exact state.

        select_name(bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature, False) # Need to select an object to get the next line to work.
        original_mode = bpy.context.active_object.mode

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass

        # Move the attach_object_to_armature object to the same collection as the armature object.
        # First confirm that they are in different collections before doing so.
        my_rig = bpy.data.objects[bpy.context.preferences.addons['attach_object_to_armature'].preferences.armature_name]
        my_obj = bpy.data.objects[bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature]
        if my_rig.users_collection[0].name != my_obj.users_collection[0].name:
            self.report({'INFO'}, '  Moving "' + bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature + '" to the same collection as "' + bpy.context.preferences.addons['attach_object_to_armature'].preferences.armature_name + '"...')
            my_rig_collection = find_collection(bpy.context, my_rig)
            my_obj_collection = find_collection(bpy.context, my_obj)
            my_rig_collection.objects.link(my_obj)  # Put my_obj in the new collection.
            my_obj_collection.objects.unlink(my_obj)  # Remove my_obj from the old collection.

        # Apply all modifiers on the object (if applicable).
        if (bpy.context.preferences.addons['attach_object_to_armature'].preferences.apply_all_modifiers):
            bpy.ops.object.select_all(action='DESELECT')
            obj = bpy.data.objects.get(bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature)
            apply_modifiers(obj)

        # Apply all transforms. Otherwise, Transfer Weights will not work correctly.
        self.report({'INFO'}, '  Applying all transforms...')
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # Parent the object to the armature.
        self.report({'INFO'}, '  Parenting "' + bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature + '" to "' + bpy.context.preferences.addons['attach_object_to_armature'].preferences.armature_name + '", Armature Deform -> With Automatic Weights...')
        select_name(bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature, False)
        select_name(bpy.context.preferences.addons['attach_object_to_armature'].preferences.armature_name, True)  # Need to select the armature last since we want to parent the object to it.
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')  # Armature Deform -> With Automatic Weights

        # Lastly, transfer weights (if applicable).
        if (len(bpy.context.preferences.addons['attach_object_to_armature'].preferences.existing_body_object_name) > 0):
            self.report({'INFO'}, '  Transferring weights...')
            select_name(bpy.context.preferences.addons['attach_object_to_armature'].preferences.existing_body_object_name, False)
            select_name(bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature, True)
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            bpy.ops.object.data_transfer(use_reverse_transfer=True, data_type='VGROUP_WEIGHTS', vert_mapping='EDGEINTERP_NEAREST', layers_select_src='NAME', layers_select_dst='ALL')

        self.report({'INFO'}, '  Done attaching "' + bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature + '" to "' + bpy.context.preferences.addons['attach_object_to_armature'].preferences.armature_name + '".')

        try:
            bpy.ops.object.mode_set(mode=original_mode)
        except:
            pass

        return {'FINISHED'}

class ATTACHOBJECTTOARMATURE_PT_Main(bpy.types.Panel):
    bl_idname = "ATTACHOBJECTTOARMATURE_PT_Main"
    bl_label = "Attach Object to Armature"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rigging"

    def draw(self, context):
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Object to Attach to Armature")
        row = box.row(align=True)
        row.prop_search(bpy.context.preferences.addons['attach_object_to_armature'].preferences, "object_name_to_attach_to_armature", bpy.data, "objects", icon='OUTLINER_OB_MESH')
        row = box.row(align=True)
        row.prop(bpy.context.preferences.addons['attach_object_to_armature'].preferences, "apply_all_modifiers")

        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Armature")
        row = box.row(align=True)
        row.prop_search(bpy.context.preferences.addons['attach_object_to_armature'].preferences, "armature_name", bpy.data, "armatures", icon='OUTLINER_OB_ARMATURE')

        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Existing Body Object")
        row = box.row(align=True)
        row.prop_search(bpy.context.preferences.addons['attach_object_to_armature'].preferences, "existing_body_object_name", bpy.data, "objects", icon='OUTLINER_OB_MESH')

        row = self.layout.row(align=True)
        row = self.layout.row(align=True)
        row.operator("aota.attach_to_armature", text='Attach Object to Armature', icon='OUTLINER_OB_ARMATURE')

        if bpy.data.objects.get(bpy.context.preferences.addons['attach_object_to_armature'].preferences.object_name_to_attach_to_armature) is None or bpy.data.objects.get(bpy.context.preferences.addons['attach_object_to_armature'].preferences.armature_name) is None:
            row.enabled = False
        elif len(bpy.context.preferences.addons['attach_object_to_armature'].preferences.existing_body_object_name) > 0 and bpy.data.objects.get(bpy.context.preferences.addons['attach_object_to_armature'].preferences.existing_body_object_name) is None:
            row.enabled = False
        else:
            row.enabled = True

def register():
    bpy.utils.register_class(AttachObjectToArmaturePreferencesPanel)
    bpy.utils.register_class(ATTACHOBJECTTOARMATURE_PT_Apply)
    bpy.utils.register_class(ATTACHOBJECTTOARMATURE_PT_Main)

def unregister():
    bpy.utils.unregister_class(AttachObjectToArmaturePreferencesPanel)
    bpy.utils.unregister_class(ATTACHOBJECTTOARMATURE_PT_Apply)
    bpy.utils.unregister_class(ATTACHOBJECTTOARMATURE_PT_Main)

if __name__ == "__main__":
    register()
