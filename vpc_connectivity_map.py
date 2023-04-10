from __future__ import annotations
from dataclasses import dataclass, field
import sys
import jinja2
import itertools

@dataclass
class Network:
    vpc: VPC = None
    elements: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    type: str = 'pub'
    def get_elements(self):
        return self.elements + self.edges + [self.vpc]

@dataclass
class VPC:
    zones: list = field(default_factory=list)
    securityGroups: list = field(default_factory=list)
    type: str = 'vpc'
    def get_elements(self):
        return self.zones + self.securityGroups

@dataclass
class Zone:
    name: str
    subnets: list = field(default_factory=list)
    elements: list = field(default_factory=list)
    type: str = 'zone'
    def get_elements(self):
        return self.subnets + self.elements

@dataclass
class Subnet:
    name: str
    IP: str
    key: str
    zone: Zone
    elements: list = field(default_factory=list)
    type: str = 'subnet'
    def get_elements(self):
        return self.elements
    def __hash__(self):
        return self.name.__hash__()

@dataclass
class SecurityGroup:
    name: str
    elements: list = field(default_factory=list)
    type: str = 'sg'
    def get_elements(self):
        return []
    def __hash__(self):
        return self.name.__hash__()

@dataclass
class Element:
    name: str
    type: str
    subnet: Subnet = None
    securityGroup: SecurityGroup = None
    attached_to: Element = None
    def get_elements(self):
        return []
    def __hash__(self):
        return self.name.__hash__()

@dataclass
class Edge:
    src: object
    dst: object
    type: str
    label: str
    geometry: str = ''
    def get_elements(self):
        return []


def build_graph():
    network = Network()
    vpc = VPC()
    us_south = Zone('us-south-1')
    subnet1 = Subnet('subnet1', '10.240.10.0/24', 'ACL1', us_south)
    subnet2 = Subnet('subnet2', '10.240.20.0/24', 'ACL2', us_south)
    subnet3 = Subnet('subnet3', '10.240.30.0/24', 'ACL3', us_south)
    securityGroup1 = SecurityGroup('sg1')
    securityGroup2 = SecurityGroup('sg2')
    securityGroup3 = SecurityGroup('sg3')
    vsi1 = Element('vsi1', 'vsi', subnet1, securityGroup1)
    vsi2 = Element('vsi2', 'vsi', subnet2, securityGroup2)
    vsi3a = Element('vsi3a', 'vsi', subnet3, securityGroup2)
    vsi3b = Element('vsi3b', 'vsi', subnet3, securityGroup3)
    public_gw = Element('public_gw', 'gateway')
    db_gw = Element('db_endpoint_gw', 'gateway', subnet3, securityGroup3)
    floating_point_ip = Element('52.118.188.231', 'floating_point', subnet2, securityGroup2, vsi2)
    internet1 = Element('142.0.0.0/8', 'internet')
    internet2 = Element('143.0.0.0/8', 'internet')
    user = Element('147.235.219.206/32', 'user')

    network.parent = None
    network.vpc = vpc

    network.elements.append(internet1)
    network.elements.append(internet2)
    network.elements.append(user)

    vpc.zones.append(us_south)

    us_south.subnets.append(subnet1)
    us_south.subnets.append(subnet2)
    us_south.subnets.append(subnet3)

    vpc.securityGroups.append(securityGroup1)
    vpc.securityGroups.append(securityGroup2)
    vpc.securityGroups.append(securityGroup3)

    us_south.elements.append(public_gw)

    subnet1.elements.append(vsi1)

    subnet2.elements.append(vsi2)
    subnet2.elements.append(floating_point_ip)

    subnet3.elements.append(vsi3a)
    subnet3.elements.append(vsi3b)
    subnet3.elements.append(db_gw)

    securityGroup1.elements.append(vsi1)
    securityGroup2.elements.append(vsi2)
    securityGroup2.elements.append(vsi3b)
    securityGroup2.elements.append(floating_point_ip)
    securityGroup3.elements.append(vsi3a)
    securityGroup3.elements.append(db_gw)

    network.edges.append(Edge(vsi1, public_gw, 'diredge',''))
    network.edges.append(Edge(public_gw, internet1, 'diredge','ICMP'))
    network.edges.append(Edge(public_gw, internet2, 'diredge','ICMP'))
    network.edges.append(Edge(floating_point_ip, internet2, 'diredge','ICMP'))
    network.edges.append(Edge(user, floating_point_ip, 'diredge','TCP 22'))
    network.edges.append(Edge(vsi2, vsi1, 'diredge',''))
    network.edges.append(Edge(vsi2, vsi3b, 'undiredge','TCP'))
    network.edges.append(Edge(vsi3b, vsi1, 'diredge',''))
    network.edges.append(Edge(vsi3b, vsi3a, 'diredge',''))
    network.edges.append(Edge(vsi3b, db_gw, 'diredge',''))
    network.edges.append(Edge(db_gw, vsi1, 'diredge',''))
    network.edges.append(Edge(vsi3a, vsi1, 'diredge',''))

    return network

##############################################################################################
@dataclass
class Row:
    positions: Positions
    elements: list = field(default_factory=list)

@dataclass
class Col:
    positions: Positions
    elements: list = field(default_factory=list)

@dataclass
class Positions:
    rows: list = field(default_factory=list)
    cols: list = field(default_factory=list)

    def get_row_index(self, row):
        return self.rows.index(row)

    def get_col_index(self, col):
        return self.cols.index(col)

    def get_n_rows(self):
        return len(self.rows)

    def get_n_cols(self):
        return len(self.cols)


def merge_a_cols(positions):
    for col1 in positions.cols:
        for col2 in positions.cols:
            if col1 != col2:
                sgs1 = set(el.securityGroup for el in col1.elements if el.securityGroup)
                sgs2 = set(el.securityGroup for el in col2.elements if el.securityGroup)
                sns1 = set(el.subnet for el in col1.elements if el.subnet)
                sns2 = set(el.subnet for el in col2.elements if el.subnet)
                if not sns1 or not sns2:
                    continue
                if sgs1 & sgs2:
                    continue
                if sns1 & sns2:
                    continue
                for el in col2.elements:
                    el.col = col1
                    positions.cols.remove(col2)
                    return True
    return False


def set_positions(network):
    positions = Positions()

    elements_lists = [[el] for zone in network.vpc.zones for subnet in zone.subnets for el in subnet.elements if not el.securityGroup]
    elements_lists += [[el] for zone in network.vpc.zones for el in zone.elements if not el.securityGroup]
    elements_lists += [sg.elements for sg in network.vpc.securityGroups]
    for elements_list in elements_lists:
        row = Row(positions)
        for el in elements_list:
            row.elements.append(el)
            el.row = row
        positions.rows.append(row)

    elements_lists = [subnet.elements for zone in network.vpc.zones for subnet in zone.subnets]
    elements_lists += [zone.elements for zone in network.vpc.zones]
    for elements_list in elements_lists:
        col = Col(positions)
        for el in elements_list:
            col.elements.append(el)
            el.col = col
        positions.cols.append(col)



    zone_elements_col_index = positions.get_col_index(network.vpc.zones[0].elements[0].col)

    positions.cols[0], positions.cols[zone_elements_col_index] = positions.cols[zone_elements_col_index], positions.cols[0]

    while merge_a_cols(positions):
        pass

    return positions

###################################################################################################


NETWORK_BORDER_DISTANCE = 40
VPC_BORDER_DISTANCE = 40
ZONE_BORDER_DISTANCE = 40
SUBNET_BORDER_DISTANCE = 40
SECURITY_GROUP_BORDER_DISTANCE = 40
NETWORK_ELEMENTS_SPACE = 4*40
ZONE_ELEMENTS_SPACE = 4*40
SUBNET_ELEMENTS_SPACE_H = 6*40
SUBNET_ELEMENTS_SPACE_W = 8*40
ICON_SIZE = 60



def set_subnet_geometry(subnet, positions):
    subnet_row_min_index = min(set(positions.get_row_index(el.row) for el in subnet.elements))
    for element in subnet.elements:
        element_row_index = positions.get_row_index(element.row) - subnet_row_min_index
        element.y = (SUBNET_ELEMENTS_SPACE_H - ICON_SIZE) / 2 + SUBNET_ELEMENTS_SPACE_H * element_row_index
        subnet_elements_in_row = [el for el in element.row.elements if el.subnet == element.subnet]
        elements_space = (SUBNET_ELEMENTS_SPACE_W - 2*SECURITY_GROUP_BORDER_DISTANCE - len(subnet_elements_in_row)*ICON_SIZE)/(len(subnet_elements_in_row) + 1)
        element.x = SECURITY_GROUP_BORDER_DISTANCE + elements_space + subnet_elements_in_row.index(element)*(elements_space + ICON_SIZE)
        element.h = ICON_SIZE
        element.w = ICON_SIZE


def set_zone_geometry(zone, positions):
    for subnet in zone.subnets:
        subnet_col_index = positions.get_col_index(subnet.elements[0].col)
        subnet_row_indexes = set(positions.get_row_index(el.row) for el in subnet.elements)
        subnet.x = ZONE_ELEMENTS_SPACE + (SUBNET_ELEMENTS_SPACE_W + SUBNET_BORDER_DISTANCE) * (subnet_col_index - 1)
        subnet.y = SUBNET_BORDER_DISTANCE + SUBNET_ELEMENTS_SPACE_H * min(subnet_row_indexes)
        subnet.h = SUBNET_ELEMENTS_SPACE_H * (max(subnet_row_indexes) - min(subnet_row_indexes) + 1)
        subnet.w = SUBNET_ELEMENTS_SPACE_W
        set_subnet_geometry(subnet, positions)
    for element in zone.elements:
        element_row_index = positions.get_row_index(element.row)
        element.x = (ZONE_ELEMENTS_SPACE - ICON_SIZE)/2
        element.y = SUBNET_BORDER_DISTANCE + (SUBNET_ELEMENTS_SPACE_H - ICON_SIZE) / 2 + SUBNET_ELEMENTS_SPACE_H * element_row_index
        element.h = ICON_SIZE
        element.w = ICON_SIZE
    zone.h = SUBNET_ELEMENTS_SPACE_H * positions.get_n_rows() + 2 * SUBNET_BORDER_DISTANCE
    n_cols_in_zone = positions.get_n_cols()
    zone.w = ZONE_ELEMENTS_SPACE + (SUBNET_ELEMENTS_SPACE_W + SUBNET_BORDER_DISTANCE) * (n_cols_in_zone - 1)


def layouting(network):
    positions = set_positions(network)
    for zone in network.vpc.zones:
        zone.x = ZONE_BORDER_DISTANCE
        zone.y = ZONE_BORDER_DISTANCE
        set_zone_geometry(zone, positions)
    for sg in network.vpc.securityGroups:
        sg_col_indexes = set(positions.get_col_index(el.col) for el in sg.elements)
        sg_row_index = positions.get_row_index(sg.elements[0].row)
        sg.y = ZONE_BORDER_DISTANCE + SUBNET_BORDER_DISTANCE + SECURITY_GROUP_BORDER_DISTANCE + sg_row_index*SUBNET_ELEMENTS_SPACE_H
        sg.x = ZONE_BORDER_DISTANCE + SECURITY_GROUP_BORDER_DISTANCE + ZONE_ELEMENTS_SPACE + (SUBNET_ELEMENTS_SPACE_W + SUBNET_BORDER_DISTANCE)*(min(sg_col_indexes) - 1)
        sg.h = SUBNET_ELEMENTS_SPACE_H - SECURITY_GROUP_BORDER_DISTANCE*2
        sg.w = (SUBNET_ELEMENTS_SPACE_W + SUBNET_BORDER_DISTANCE) * (max(sg_col_indexes) - min(sg_col_indexes) + 1) - SUBNET_BORDER_DISTANCE - 2* SECURITY_GROUP_BORDER_DISTANCE
    for element in network.elements:
        element.x = (NETWORK_ELEMENTS_SPACE - ICON_SIZE)/2
        element.y = (NETWORK_ELEMENTS_SPACE - ICON_SIZE)/2 + NETWORK_ELEMENTS_SPACE * network.elements.index(element)
        element.h = ICON_SIZE
        element.w = ICON_SIZE
    network.vpc.x = NETWORK_ELEMENTS_SPACE
    network.vpc.y = VPC_BORDER_DISTANCE
    network.vpc.w = sum(zone.w for zone in network.vpc.zones) + ZONE_BORDER_DISTANCE*(len(network.vpc.zones) + 1)
    network.vpc.h = max(zone.h for zone in network.vpc.zones) + ZONE_BORDER_DISTANCE*2
    network.x = NETWORK_BORDER_DISTANCE
    network.y = NETWORK_BORDER_DISTANCE
    network.w = network.vpc.w + NETWORK_ELEMENTS_SPACE + VPC_BORDER_DISTANCE
    network.h = network.vpc.h + 2*VPC_BORDER_DISTANCE

#################################################################################################################

id_counter = 100
def set_ids(me):
    global id_counter
    me.id = id_counter
    me.parent_id = me.parent.id if me.parent else ''
    id_counter += 5
    for child in me.get_elements():
        child.parent = me
        set_ids(child)


def get_jinja_info(me):
    if 'diredge' not in me.type:
        me.geometry = f'x="{me.x}" y="{me.y}" width="{me.w}" height="{me.h}"'
    return [me] + list(itertools.chain(*[get_jinja_info(child) for child in me.get_elements()]))

if __name__ == "__main__":

    file_name = sys.argv[1]
    templateLoader = jinja2.FileSystemLoader(searchpath='./')
    templateEnv = jinja2.Environment(loader=templateLoader)
    template = templateEnv.get_template(file_name)

    network = build_graph()
    set_ids(network)
    layouting(network)
    jinja_info = get_jinja_info(network)
    outputText = template.render(elements=jinja_info)
    with open('out.drawio', 'w') as f:
        f.write(outputText)
