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
    Key: str
    elements: list = field(default_factory=list)
    type: str = 'subnet'
    def get_elements(self):
        return self.elements

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
    subnet1 = Subnet('subnet1', '10.240.10.0/24', 'ACL1')
    subnet2 = Subnet('subnet2', '10.240.20.0/24', 'ACL2')
    subnet3 = Subnet('subnet3', '10.240.30.0/24', 'ACL3')
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

@dataclass
class Layer:
    elements: list = field(default_factory=list)


def set_positions(network):
    for zone in network.vpc.zones:
        for subnet in zone.subnets:
            subnet.el_to_layers = {
                el: el.attached_to.securityGroup if el.attached_to else el.securityGroup if el.securityGroup else el for
                el in subnet.elements}
            layers = set(subnet.el_to_layers.values())
            subnet.layers = {layer: [el for el in subnet.el_to_layers.keys() if subnet.el_to_layers[el] == layer] for
                             layer in layers}
    all_layers = list(set(itertools.chain(*[subnet.layers.keys() for zone in network.vpc.zones for subnet in zone.subnets])))
    return all_layers


def set_subnet_geometry(subnet, all_zone_layers):
    for element in subnet.elements:
        element.y = (SUBNET_ELEMENTS_SPACE_H - ICON_SIZE) / 2 + SUBNET_ELEMENTS_SPACE_H * all_zone_layers.index(subnet.el_to_layers[element])
    for layer, elements in subnet.layers.items():
        elements_space = (SUBNET_ELEMENTS_SPACE_W - 2*SECURITY_GROUP_BORDER_DISTANCE - len(elements)*ICON_SIZE)/(len(elements) + 1)
        for el in elements:
            el.x = SECURITY_GROUP_BORDER_DISTANCE + elements_space + elements.index(el)*(elements_space + ICON_SIZE)
    for element in subnet.elements:
        element.h = ICON_SIZE
        element.w = ICON_SIZE


def set_zone_geometry(zone, all_zone_layers):
    for subnet in zone.subnets:
        subnet.x = ZONE_ELEMENTS_SPACE + (SUBNET_ELEMENTS_SPACE_W + SUBNET_BORDER_DISTANCE) * zone.subnets.index(subnet)
        subnet.y = SUBNET_BORDER_DISTANCE
        subnet.h = SUBNET_ELEMENTS_SPACE_H * len(all_zone_layers)
        subnet.w = SUBNET_ELEMENTS_SPACE_W
        set_subnet_geometry(subnet, all_zone_layers)
    for element in zone.elements:
        element.x = (ZONE_ELEMENTS_SPACE - ICON_SIZE)/2
        element.y = (ZONE_ELEMENTS_SPACE - ICON_SIZE)/2 + (ZONE_ELEMENTS_SPACE - ICON_SIZE)/2 * zone.elements.index(element)
        element.h = ICON_SIZE
        element.w = ICON_SIZE
    zone.h = max(subnet.h for subnet in zone.subnets) + 2 * SUBNET_BORDER_DISTANCE
    zone.w = ZONE_ELEMENTS_SPACE + (SUBNET_ELEMENTS_SPACE_W + SUBNET_BORDER_DISTANCE) * len(zone.subnets)


def layouting(network):
    all_layers = set_positions(network)
    for zone in network.vpc.zones:
        zone.x = ZONE_BORDER_DISTANCE
        zone.y = ZONE_BORDER_DISTANCE
        set_zone_geometry(zone, all_layers)
    for sg in network.vpc.securityGroups:
        sg.y = ZONE_BORDER_DISTANCE + SUBNET_BORDER_DISTANCE + SECURITY_GROUP_BORDER_DISTANCE + all_layers.index(sg)*SUBNET_ELEMENTS_SPACE_H
        sg.x = ZONE_BORDER_DISTANCE + SECURITY_GROUP_BORDER_DISTANCE
        sg.h = SUBNET_ELEMENTS_SPACE_H - SECURITY_GROUP_BORDER_DISTANCE*2
        sg.w = sum(zone.w for zone in network.vpc.zones) + ZONE_BORDER_DISTANCE*(len(network.vpc.zones)- 1 ) - SECURITY_GROUP_BORDER_DISTANCE * 2 - SUBNET_BORDER_DISTANCE
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
