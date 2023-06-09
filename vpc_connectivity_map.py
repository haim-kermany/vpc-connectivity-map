from __future__ import annotations
from dataclasses import dataclass, field
import sys
import os
import shutil
import jinja2
import jsonpickle
import json
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
    def __hash__(self):
        return self.id.__hash__()

@dataclass
class Subnet:
    name: str
    IP: str
    key: str
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
    securityGroup: SecurityGroup = None
    public_gw: Element = None
    def get_elements(self):
        return []
    def __hash__(self):
        return self.name.__hash__()
    def __hash__(self):
        return self.name.__hash__()
    def __lt__(self, other):
        return self.name < other.name
@dataclass
class Edge:
    src: object
    dst: object
    type: str
    label: str
    points: list = field(default_factory=list)
    def __hash__(self):
        return self.src.name.__hash__() + self.dst.name.__hash__()
    def get_elements(self):
        return []
    def get_name(self):
        return f'{self.src.name}->{self.dst.name}'



##############################################################################################
@dataclass
class Row:
    positions: Positions
    elements: list = field(default_factory=list)

@dataclass
class Col:
    positions: Positions
    zone: Zone
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
            if col1 != col2 and col1.zone == col2.zone:
                sgs1 = set(el.securityGroup for el in col1.elements if el.securityGroup)
                sgs2 = set(el.securityGroup for el in col2.elements if el.securityGroup)
                parents1 = [el.parent for el in col1.elements]
                parents2 = [el.parent for el in col2.elements]
                if not parents1 or not parents2:
                    continue
                if not isinstance(parents1[0], Subnet) or not isinstance(parents2[0], Subnet):
                    continue
                if sgs1 & sgs2:
                    continue
                if [per for per in parents1 if per in parents2]:
                    continue
                for el in col2.elements:
                    el.col = col1
                    col1.elements.append(el)
                positions.cols.remove(col2)
                return True
    return False

def merge_a_rows(positions):
    row_to_parameters = [(row, (not sum(set(isinstance(el.parent, Subnet) for el in row.elements)), len(row.elements))) for row in positions.rows]
    row_to_parameters.sort(key=lambda r: r[1])
    sorted_rows = [r[0] for r in row_to_parameters]
    for row1 in sorted_rows:
        for row2 in sorted_rows:
            if row1 != row2:
                parents1 = set(el.parent for el in row1.elements)
                parents2 = set(el.parent for el in row2.elements)
                cols1 = [el.col for el in row1.elements]
                cols2 = [el.col for el in row2.elements]
                if [col for col in cols1 if col in cols2]:
                    continue
                if parents1 & parents2:
                    continue
                for el in row2.elements:
                    el.row = row1
                    row1.elements.append(el)
                positions.rows.remove(row2)
                return True
    return False


def flip_a_clos(positions):
    for row in positions.rows:
        row_sgs = set(el.securityGroup for el in row.elements if el.securityGroup)
        if len(row_sgs) > 1:
            sg_cols = [sorted(list(set(positions.get_col_index(el.col) for el in sg.elements))) for sg in row_sgs]
            all_cols = sum(sg_cols,[])
            if len(set( positions.cols[col].zone for col in sum(sg_cols,[]))) > 1:
                continue
            sg_cols.sort(key=lambda sg: sg[0])
            for sg1, sg2 in zip(sg_cols[0:-1], sg_cols[1:]):
                if sg1[-1] > sg2[0]:
                    all_cols_indexes = sg1 + sg2
                    all_cols_new_indexes = sorted(all_cols_indexes)
                    old_col = positions.cols.copy()
                    for o, n in zip(all_cols_indexes, all_cols_new_indexes):
                        positions.cols[n] = old_col[o]
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

    for zone in network.vpc.zones:
        for subnet_or_zone in [zone] + zone.subnets:
            elements_list = subnet_or_zone.elements
            col = Col(positions, zone)
            for el in elements_list:
                col.elements.append(el)
                el.col = col
            positions.cols.append(col)
    if network.vpc.zones[0].elements:
        zone_elements_col_index = positions.get_col_index(network.vpc.zones[0].elements[0].col)
        positions.cols[0], positions.cols[zone_elements_col_index] = positions.cols[zone_elements_col_index], positions.cols[0]
    return positions

def minimize_positions(positions, max_steps):
    steps = 0
    if steps >= max_steps:
        return True
    while merge_a_cols(positions):
        steps += 1
        if max_steps < steps:
            return True
        pass
    while merge_a_rows(positions):
        steps += 1
        if max_steps < steps:
            return True
        pass
    while flip_a_clos(positions):
        steps += 1
        if max_steps < steps:
            return True
        pass
    return False


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
INROW_DISTANCE = (ICON_SIZE + 40)/2


def set_subnet_geometry(subnet, positions):
    inrow_geometry = [
        [],
        [(0, 0)],
        [(-INROW_DISTANCE, 0), (INROW_DISTANCE, 0)],
        [(INROW_DISTANCE, -INROW_DISTANCE), (-INROW_DISTANCE, 0), (INROW_DISTANCE, INROW_DISTANCE)],
    ]
    subnet_row_min_index = min(set(positions.get_row_index(el.row) for el in subnet.elements))
    for element in subnet.elements:
        subnet_elements_in_row = [el for el in element.row.elements if el.parent == element.parent]
        element_index = subnet_elements_in_row.index(element)
        element_row_index = positions.get_row_index(element.row) - subnet_row_min_index
        element.y = (SUBNET_ELEMENTS_SPACE_H - ICON_SIZE)/2 + inrow_geometry[len(subnet_elements_in_row)][element_index][1] + (SUBNET_ELEMENTS_SPACE_H + SUBNET_BORDER_DISTANCE) * element_row_index
        element.x = (SUBNET_ELEMENTS_SPACE_W - ICON_SIZE)/2 + inrow_geometry[len(subnet_elements_in_row)][element_index][0]
        element.h = ICON_SIZE
        element.w = ICON_SIZE


def set_zone_geometry(zone, positions):
    zone_cols = [i for i in range(len(positions.cols)) if positions.cols[i].zone == zone]
    for subnet in zone.subnets:
        subnet_col_index = positions.get_col_index(subnet.elements[0].col)
        subnet_row_indexes = set(positions.get_row_index(el.row) for el in subnet.elements)
        subnet.x = ZONE_ELEMENTS_SPACE + (SUBNET_ELEMENTS_SPACE_W + SUBNET_BORDER_DISTANCE) * (subnet_col_index - min(zone_cols)- 1)
        subnet.y = (SUBNET_BORDER_DISTANCE + SUBNET_ELEMENTS_SPACE_H) * min(subnet_row_indexes) + SUBNET_BORDER_DISTANCE
        subnet.h = (SUBNET_ELEMENTS_SPACE_H  + SUBNET_BORDER_DISTANCE)* (max(subnet_row_indexes) - min(subnet_row_indexes) + 1) - SUBNET_BORDER_DISTANCE
        subnet.w = SUBNET_ELEMENTS_SPACE_W
        set_subnet_geometry(subnet, positions)
    for element in zone.elements:
        element_row_index = positions.get_row_index(element.row)
        element.x = (ZONE_ELEMENTS_SPACE - ICON_SIZE)/2
        element.y = SUBNET_BORDER_DISTANCE + (SUBNET_ELEMENTS_SPACE_H - ICON_SIZE) / 2 + (SUBNET_ELEMENTS_SPACE_H + SUBNET_BORDER_DISTANCE) * element_row_index
        element.h = ICON_SIZE
        element.w = ICON_SIZE
    zone.h = (SUBNET_ELEMENTS_SPACE_H + SUBNET_BORDER_DISTANCE) * positions.get_n_rows() + SUBNET_BORDER_DISTANCE
    n_cols_in_zone = max(zone_cols) - min(zone_cols) + 1
    zone.w = ZONE_ELEMENTS_SPACE + (SUBNET_ELEMENTS_SPACE_W + SUBNET_BORDER_DISTANCE) * (n_cols_in_zone - 1)


def set_geometry(network, positions):
    network.vpc.x = NETWORK_ELEMENTS_SPACE
    network.vpc.y = VPC_BORDER_DISTANCE
    network.x = NETWORK_BORDER_DISTANCE
    network.y = NETWORK_BORDER_DISTANCE

    current_zone_x = ZONE_BORDER_DISTANCE
    for zone in network.vpc.zones:
        zone.x = current_zone_x
        zone.y = ZONE_BORDER_DISTANCE
        set_zone_geometry(zone, positions)
        current_zone_x += zone.w + ZONE_BORDER_DISTANCE
    for sg in network.vpc.securityGroups:
        sg_row_index = positions.get_row_index(sg.elements[0].row)
        sg.y = ZONE_BORDER_DISTANCE + SUBNET_BORDER_DISTANCE + sg_row_index*(SUBNET_ELEMENTS_SPACE_H + SUBNET_BORDER_DISTANCE) + SECURITY_GROUP_BORDER_DISTANCE
        sg.h = SUBNET_ELEMENTS_SPACE_H - SECURITY_GROUP_BORDER_DISTANCE*2

        elements_abs_x = [get_element_abs_position(el)[0] for el in sg.elements]
        sg.x = min(elements_abs_x) - SECURITY_GROUP_BORDER_DISTANCE - get_element_abs_position(network.vpc)[0]
        sg.w = max(elements_abs_x) - min(elements_abs_x) + 2*SECURITY_GROUP_BORDER_DISTANCE + ICON_SIZE
    for element in network.elements:
        element.x = (NETWORK_ELEMENTS_SPACE - ICON_SIZE)/2
        element.y = (NETWORK_ELEMENTS_SPACE - ICON_SIZE)/2 + NETWORK_ELEMENTS_SPACE * network.elements.index(element)
        element.h = ICON_SIZE
        element.w = ICON_SIZE
    network.vpc.w = sum(zone.w for zone in network.vpc.zones) + ZONE_BORDER_DISTANCE*(len(network.vpc.zones) + 1)
    network.vpc.h = max(zone.h for zone in network.vpc.zones) + ZONE_BORDER_DISTANCE*2
    network.w = network.vpc.w + NETWORK_ELEMENTS_SPACE + VPC_BORDER_DISTANCE
    network.h = network.vpc.h + 2*VPC_BORDER_DISTANCE






###########################################################################################

def get_element_abs_position(el):
    if not el.parent:
        return (NETWORK_BORDER_DISTANCE,NETWORK_BORDER_DISTANCE)
    return (get_element_abs_position(el.parent)[0] + el.x, get_element_abs_position(el.parent)[1] + el.y)


MATRIX_GRANOLATITY = ICON_SIZE
def get_el_abs_posiotions(me, matrix):
    if isinstance(me, Element):
        x,y = get_element_abs_position(me)
        matrix[int(y/MATRIX_GRANOLATITY)][int(x/MATRIX_GRANOLATITY)][0].add(me)
    for child in me.get_elements():
        get_el_abs_posiotions(child,matrix)

def get_edges_abs_posiotions(network, matrix):
    for edge in network.edges:
        x1, y1 = get_element_abs_position(edge.src)
        x2, y2 = get_element_abs_position(edge.dst)
        n_steps = int(max(abs(x2 - x1), abs(y2 - y1))/MATRIX_GRANOLATITY*2) + 1
        x_step = (x2 - x1)/n_steps
        y_step = (y2 - y1)/n_steps
        for x, y in zip([x1+x_step*i for i in range(n_steps)], [y1+y_step*i for i in range(n_steps)]):
            matrix[int(y / MATRIX_GRANOLATITY)][int(x / MATRIX_GRANOLATITY)][1].add(edge)

def get_matrix(network):
    h = network.h/MATRIX_GRANOLATITY
    w = network.w/MATRIX_GRANOLATITY
    matrix = [[(set(),set()) for x in range(int(w))] for y in range(int(h))]
    get_el_abs_posiotions(network,matrix)
    get_edges_abs_posiotions(network,matrix)
    edge_to_break = set()
    for y in range(len(matrix)):
        for x in range(len(matrix[y])):
            if matrix[y][x][0] and matrix[y][x][1]:
                for edge in matrix[y][x][1]:
                    if edge.src not in matrix[y][x][0] and edge.dst not in matrix[y][x][0]:
                        print(edge.get_name(), set(e.name for e in matrix[y][x][0]))
                        edge_to_break.add(edge)
    for edge in edge_to_break:
        x1, y1 = get_element_abs_position(edge.src)
        x2, y2 = get_element_abs_position(edge.dst)
        if abs(x2 - x1) > abs(y2 - y1):
            point_y = min(y1,y2) - SUBNET_ELEMENTS_SPACE_H/2 + ICON_SIZE
            point_x = (x1 + x2)/2
        else:
            point_x = min(x1, x2) - SUBNET_ELEMENTS_SPACE_H/2 + ICON_SIZE
            point_y = (y1 + y2) / 2
        edge.points = [(point_x, point_y)]
    return matrix

def break_overlaping(network):
    matrix = get_matrix(network)

def add_fip_edge_point(network):
    type_to_point = {
        'ni_vsi_fp': (-50, +40),
        'ni_fp': (-40, +50)
    }
    fip_to_n_con = {}
    for edge in network.edges:
        if edge.src in network.elements and 'fp' in edge.dst.type:
            x, y = get_element_abs_position(edge.dst)
            ncon = fip_to_n_con.get(edge.dst, 0)
            edge.points.append((x + type_to_point[edge.dst.type][0], y + type_to_point[edge.dst.type][1] - ncon*4))
            edge.points.append((x + type_to_point[edge.dst.type][0] + 40, y + type_to_point[edge.dst.type][1] - ncon*4))
            ncon += 1
            fip_to_n_con[edge.dst] = ncon
        elif edge.dst in network.elements and 'fp' in edge.src.type:
            ncon = fip_to_n_con.get(edge.src, 0)
            x, y = get_element_abs_position(edge.src)
            edge.points.insert(0, (x + type_to_point[edge.src.type][0], y + type_to_point[edge.src.type][1] - ncon*4))
            edge.points.insert(0, (x + type_to_point[edge.src.type][0] + 40, y + type_to_point[edge.src.type][1] - ncon*4))
            ncon += 1
            fip_to_n_con[edge.src] = ncon
        elif edge.dst in network.elements and edge.src.public_gw:
            ncon = fip_to_n_con.get(edge.src.public_gw, 0)
            x, y = get_element_abs_position(edge.src.public_gw)
            edge.points.insert(0, (x, y + ICON_SIZE/2 - ncon*4))
            edge.points.insert(0, (x + ICON_SIZE, y  + ICON_SIZE/2 - ncon*4))
            ncon += 1
            fip_to_n_con[edge.src.public_gw] = ncon



def layouting(network, max_steps):
    positions = set_positions(network)
    r = minimize_positions(positions, max_steps)
    set_geometry(network, positions)
    for edge in network.edges:
        edge.points.clear()
    break_overlaping(network)
    add_fip_edge_point(network)
    return r



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

def set_sgs(network):
    for sg in network.vpc.securityGroups:
        for el in sg.elements:
            el.securityGroup = sg

def get_jinja_info(me):
    if 'edge' not in me.type:
        me.geometry = f'x="{me.x}" y="{me.y}" width="{me.w}" height="{me.h}"'
    return [me] + list(itertools.chain(*[get_jinja_info(child) for child in me.get_elements()]))



def read_connectivity(file):

    with open(file) as f:
        configs = json.load(f)
    architecture = configs['architecture']
    connectivity = configs['connectivity']
    network = Network()
    network.vpc = VPC()
    network.vpc.zones = [Zone(name) for name in set( node['zone'] for node in architecture['NodeSets'] if 'zone' in node )]
    uid_to_subnet = {}
    el_uid_to_subnet = {}
    el_uid_to_zone = {}
    el_addr_to_sg = {}
    el_uid_to_sg = {}
    uid_to_el = {}
    sg_filters = {filter['name']: filter['members'].split(',') for filter in architecture['Filters'] if filter['kind'] == 'SG' and filter['members']}
    for sg_name, members in sg_filters.items():
        sg = SecurityGroup(sg_name)
        network.vpc.securityGroups.append(sg)
        for addr in members:
            el_addr_to_sg[addr] = sg
    acl_filters = {filter['subnets']: filter['name'] for filter in architecture['Filters'] if filter['kind'] == 'NACL'}
    for nodeset in [node for node in architecture['NodeSets'] if node['kind'] == 'Subnet']:
        subnet_name = nodeset['name']
        subnet_nodes = [node for node in architecture['Nodes'] if node.get('subnetUID', '') == nodeset['uid']]
        subnet_address = nodeset['cidr']
        subnet_acl_name = acl_filters.get(subnet_address, 'no_acl_name')
        subnet = Subnet(subnet_name, subnet_address, subnet_acl_name)
        uid_to_subnet[nodeset['uid']] = subnet
        zone = [zone for zone in network.vpc.zones if zone.name == nodeset['zone']][0]
        zone.subnets.append(subnet)
        for node in subnet_nodes:
            if node['kind'] == 'NetworkInterface':
                el = Element(node['vsiName'], 'ni')
                uid_to_el[node['uid']] = el
                subnet.elements.append(el)
                el_uid_to_subnet[node['uid']] = subnet
                el_uid_to_zone[node['uid']] = zone
                node_address = node['address']
                if node_address in el_addr_to_sg:
                    el_addr_to_sg[node_address].elements.append(el)
                    el_uid_to_sg[node['uid']] = el_addr_to_sg[node_address]
    for nodeset in [node for node in architecture['NodeSets'] if node['kind'] == 'VSI']:
        vsi_name = nodeset['name']
        vsi_elements_uids = nodeset['nodes'].split(',')
        if len(vsi_elements_uids) > 1:
            el = Element(vsi_name, 'vsi')
            el.vsi_name = vsi_name
            el_uid_to_zone[vsi_elements_uids[0]].elements.append(el)
            for uid in vsi_elements_uids:
                e = Edge(el, uid_to_el[uid], 'linkedge','')
                network.edges.append(e)

        elif len(vsi_elements_uids) == 1:
            uid_to_el[vsi_elements_uids[0]].type += '_vsi'
        else:
            print('VSI without nodes')
    for router in architecture['Routers']:
        attached_to = router['attached_to'].split(',')
        attached_to.remove('')
        if router['kind'] == 'PublicGateway':
            el = Element(router['name'], 'gateway')
            el_uid_to_zone[attached_to[0]].elements.append(el)
            for at in attached_to:
                uid_to_el[at].public_gw = el
        elif router['kind'] == 'FloatingIP':
            uid_to_el[attached_to[0]].type += '_fp'

        else:
            print('unknown router')
            continue
        uid_to_el[router['uid']] = el

    for node in [node for node in architecture['Nodes'] if node['kind'] == 'ExternalNetwork']:
        el = Element(node['cidr'], 'internet')
        network.elements.append(el)
        uid_to_el[node['cidr']] = el

    for edge in connectivity:
        src_id = edge['src']['ResourceUID'] if edge['src']['ResourceUID'] else edge['src']['CidrStr']
        dst_id = edge['dst']['ResourceUID'] if edge['dst']['ResourceUID'] else edge['dst']['CidrStr']
        e = Edge(uid_to_el[src_id], uid_to_el[dst_id], 'diredge', edge['conn'] if edge['conn'] != 'All Connections' else '')
        network.edges.append(e)

    dir_edges_to_remove = [e for e in network.edges if Edge(e.dst,e.src,'diredge',e.label) in network.edges]
    dir_edges_to_stay = [e for e in network.edges if e not in dir_edges_to_remove]
    undir_edges_to_add = [Edge(e.dst, e.src, 'undiredge', e.label) for e in dir_edges_to_remove if e.src < e.dst]
    network.edges = dir_edges_to_stay + undir_edges_to_add

    network.elements = [el for el in network.elements if el in [e.src for e in network.edges] + [e.dst for e in network.edges]]

    new_sgs = []
    for sg in network.vpc.securityGroups:
        if len(sg.elements) > 6:
            names = {e.name: e for e in sg.elements}
            inits = set(n[0] for n in names)
            for init in inits:
                new_sg = SecurityGroup(sg.name)
                for el in [el for n,el in names.items() if n.startswith(init)]:
                    new_sg.elements.append(el)
                new_sgs.append(new_sg)
        else:
            new_sgs.append(sg)
    network.vpc.securityGroups = new_sgs

    return network


###############################################################################################

if __name__ == "__main__":

    file_name = sys.argv[1]
    templateLoader = jinja2.FileSystemLoader(searchpath='./')
    templateEnv = jinja2.Environment(loader=templateLoader)
    template = templateEnv.get_template(file_name)


    files = [
           'examples/sg_testing1/out_sg_testing1.json',
           'examples/acl_testing3/out_acl_testing3.json',
           'examples/demo/out_demo2.json',
           'examples/multinis/out_multiNIS.json',
           'examples/karen_25_4/result.json',
    ]
    for file in files:
        network_name = os.path.basename(file)
        network = read_connectivity(file)
        network.parent = None
        set_sgs(network)
        set_ids(network)
        steps = 0
        dir = 'examples/' + network_name
        if os.path.isdir(dir):
            shutil.rmtree(dir)
        os.mkdir(dir)
        while layouting(network, steps):
            print('xxxxxxxxxxxxxxxxxxx',dir,steps)
            jinja_info = get_jinja_info(network)
            outputText = template.render(elements=jinja_info)
            with open(dir + '/' + network_name + str(steps) + '.drawio', 'w') as f:
                f.write(outputText)
            steps += 1
