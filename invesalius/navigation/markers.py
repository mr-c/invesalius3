#--------------------------------------------------------------------------
# Software:     InVesalius - Software de Reconstrucao 3D de Imagens Medicas
# Copyright:    (C) 2001  Centro de Pesquisas Renato Archer
# Homepage:     http://www.softwarepublico.gov.br
# Contact:      invesalius@cti.gov.br
# License:      GNU - GPL 2 (LICENSE.txt/LICENCA.txt)
#--------------------------------------------------------------------------
#    Este programa e software livre; voce pode redistribui-lo e/ou
#    modifica-lo sob os termos da Licenca Publica Geral GNU, conforme
#    publicada pela Free Software Foundation; de acordo com a versao 2
#    da Licenca.
#
#    Este programa eh distribuido na expectativa de ser util, mas SEM
#    QUALQUER GARANTIA; sem mesmo a garantia implicita de
#    COMERCIALIZACAO ou de ADEQUACAO A QUALQUER PROPOSITO EM
#    PARTICULAR. Consulte a Licenca Publica Geral GNU para obter mais
#    detalhes.
#--------------------------------------------------------------------------

import invesalius.session as ses
from invesalius.pubsub import pub as Publisher
from invesalius.data.markers.marker import MarkerType, Marker
from invesalius.utils import Singleton
from invesalius.navigation.robot import Robot, RobotObjective


class MarkersControl(metaclass=Singleton):
    def __init__(self):
        self.list = []
        self.nav_status = False
        self.robot = None
        self.control = None

    def SaveState(self):
        state = [marker.to_dict() for marker in self.list]

        session = ses.Session()
        session.SetState('markers', state)

    def LoadState(self):
        session = ses.Session()
        state = session.GetState('markers')

        if state is None:
            return

        for d in state:
            marker = Marker().from_dict(d)
            self.AddMarker(marker, render=False)

    def AddMarker(self, marker, render=True):
        """
        Given a marker object, add it to the list of markers and render the new marker.
        """
        marker.marker_id = len(self.list)
        self.list.append(marker)

        Publisher.sendMessage('Add marker', marker=marker, render=render)

        if marker.is_target:
            self.SetTarget(marker.marker_id)

        if marker.is_point_of_interest:
            self.SetPointOfInterest(marker.marker_id)
            Publisher.sendMessage('Set as Efield target at cortex', position=marker.position,
                                  orientation=marker.orientation)

        self.SaveState()

    def Clear(self):
        for marker in reversed(self.list):
            self.DeleteMarker(marker.marker_id)
        self.SaveState()

    def DeleteMarker(self, marker_id):
        marker = self.list[marker_id]

        if marker.is_target:
            self.UnsetTarget(marker_id)
        if marker.is_point_of_interest:
            self.UnsetPointOfInterest(marker_id)

        Publisher.sendMessage('Delete marker', marker=marker)
        del self.list[marker_id]
        for idx, m in enumerate(self.list):
            m.marker_id = idx

        self.SaveState()

    def SetTarget(self, marker_id):

        # Set robot objective to NONE when a new target is selected. This prevents the robot from
        # automatically moving to the new target (which would be the case if robot objective was previously
        # set to TRACK_TARGET). Preventing the automatic moving makes robot movement more explicit and predictable.
        self.robot.SetObjective(RobotObjective.NONE)

        prev_target = self.FindTarget()

        # If the new target is same as the previous do nothing.
        if prev_target and prev_target.marker_id == marker_id:
            return

        # Unset the previous target
        if prev_target is not None:
            self.UnsetTarget(prev_target.marker_id)

        # Set new target
        marker = self.list[marker_id]
        marker.is_target = True
        self.control.target_selected = True

        Publisher.sendMessage('Set target', marker=marker)
        Publisher.sendMessage('Set target transparency', marker=marker, transparent=True)

        self.SaveState()

    def SetPointOfInterest(self, marker_id):
        # Find the previous point of interest
        prev_poi = self.FindPointOfInterest()

        # If the new point of interest is same as the previous do nothing
        if prev_poi.marker_id == marker_id:
            return

        # Unset the previous point of interest
        if prev_poi is not None:
            self.UnsetPointOfInterest(prev_poi.marker_id)

        # Set the new point of interest
        marker = self.list[marker_id]
        marker.is_point_of_interest = True

        Publisher.sendMessage('Set point of interest', marker=marker)

        self.SaveState()

    def UnsetTarget(self, marker_id):
        marker = self.list[marker_id]
        marker.is_target = False

        Publisher.sendMessage('Set target transparency', marker=marker, transparent=False)
        Publisher.sendMessage('Unset target', marker=marker)

        self.SaveState()

    def UnsetPointOfInterest(self, marker_id):
        marker = self.list[marker_id]
        marker.is_point_of_interest = False

        Publisher.sendMessage('Set target transparency', marker=marker, transparent=False)
        Publisher.sendMessage('Unset point of interest', marker=marker)

        self.SaveState()

    def FindTarget(self):
        """
        Return the marker currently selected as target (there
        should be at most one).
        """
        for marker in self.list:
            if marker.is_target:
                return marker

        return None

    def FindPointOfInterest(self):
        for marker in self.list:
            if marker.is_point_of_interest:
                return marker

        return None

    def ChangeLabel(self, marker, new_label):
        marker.label = str(new_label)
        Publisher.sendMessage('Update marker label', marker=marker)

        self.SaveState()

    def ChangeColor(self, marker, new_color):
        """
        :param marker: instance of Marker
        :param new_color: digital 8-bit per channel rgb
        """
        assert len(new_color) == 3
        marker.colour8bit = new_color
        Publisher.sendMessage('Set new color', marker=marker, new_color=new_color)

        self.SaveState()

    def GetNextMarkerLabel(self):
        """
        Return a label for the next marker that is not already in use, in the form 'New marker N',
        where N is a number.
        """
        current_labels = [m.label for m in self.list]
        label = 'New marker'
        i = 1
        while label in current_labels:
            i += 1
            label = 'New marker ' + str(i)

        return label

    def DeleteBrainTargets(self):
        def find_brain_target():
            for marker in self.list:
                if marker.marker_type == MarkerType.BRAIN_TARGET:
                    return marker
            return None

        condition = True
        while condition:
            brain_target = find_brain_target()
            if find_brain_target() is not None:
                self.DeleteMarker(brain_target.marker_id)
            else:
                condition = False
