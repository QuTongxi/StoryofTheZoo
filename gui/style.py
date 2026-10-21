"""Clean visitor-service visual language and scalable line icons."""
import math
import pygame

INK = (30, 55, 49)
GREEN = (41, 91, 75)
MUTED = (111, 128, 119)
PAPER = (248, 249, 243)
LINE = (206, 218, 207)
ACCENT = (202, 162, 83)
RED = (170, 70, 59)

ICONS = {'settings': 'settings', 'inventory': 'bag', 'rules': 'book', 'flowchart': 'flow',
         'achievements': 'trophy', 'save': 'save', 'load': 'load', 'rollback': 'back',
         'history': 'book', 'voice': 'sound', 'new_game': 'play', 'continue_game': 'play',
         'chapter_continue': 'play', 'to_title': 'home', 'close': 'close', 'quit': 'exit',
         'use_item': 'play', 'load_point': 'play', 'help': 'book', 'restart': 'back',
         'save_slot': 'save', 'load_slot': 'load', 'bookmark': 'bookmark'}


def icon(surface, name, rect, color=GREEN):
    r = pygame.Rect(rect)
    def pt(x,y):
        return (round(r.x+x*r.width/24), round(r.y+y*r.height/24))
    width = max(1, round(r.width/14))
    def line(points, closed=False):
        pygame.draw.lines(surface,color,closed,[pt(*p) for p in points],width)
    def box(x,y,w,h):
        pygame.draw.rect(surface,color,pygame.Rect(pt(x,y),(round(w*r.width/24),round(h*r.height/24))),width,border_radius=3)
    def circle(x,y,radius):
        pygame.draw.circle(surface,color,pt(x,y),max(1,round(radius*r.width/24)),width)
    if name == 'settings':
        circle(12,12,7); circle(12,12,2)
        for i in range(8):
            a=i*math.pi/4
            line([(12+7*math.cos(a),12+7*math.sin(a)),(12+10*math.cos(a),12+10*math.sin(a))])
    elif name == 'bag':
        box(5,6,14,15); line([(8,6),(8,3),(16,3),(16,6)]); box(8,13,8,6)
    elif name == 'map':
        line([(2,5),(8,2),(16,5),(22,2),(22,19),(16,22),(8,19),(2,22)],True)
        line([(8,2),(8,19)]); line([(16,5),(16,22)])
    elif name in ('book','bookmark'):
        if name == 'bookmark':
            line([(6,3),(18,3),(18,22),(12,17),(6,22)],True)
        else:
            line([(12,5),(4,3),(2,4),(2,20),(12,22),(22,20),(22,4),(20,3),(12,5),(12,22)])
    elif name == 'flow':
        box(8,1,8,6); box(1,17,8,6); box(15,17,8,6)
        line([(12,7),(12,12),(5,12),(5,17)]); line([(12,12),(19,12),(19,17)])
    elif name == 'trophy':
        line([(6,3),(18,3),(17,12),(12,16),(7,12)],True)
        line([(6,5),(2,5),(2,10),(7,12)]); line([(18,5),(22,5),(22,10),(17,12)])
        line([(12,16),(12,21)]); line([(7,22),(17,22)])
    elif name == 'save':
        line([(3,2),(18,2),(22,6),(22,22),(3,22)],True); box(7,2,10,7); box(7,14,11,8)
    elif name == 'load':
        line([(2,7),(2,3),(10,3),(13,7),(22,7),(20,22),(4,22)],True); line([(3,11),(21,11)])
    elif name in ('back','exit'):
        line([(11,5),(4,12),(11,19)]); line([(4,12),(21,12)])
    elif name == 'play':
        line([(7,3),(21,12),(7,21)],True)
    elif name == 'home':
        line([(2,11),(12,2),(22,11)]); line([(5,9),(5,22),(19,22),(19,9)]); box(10,15,4,7)
    elif name == 'close':
        line([(5,5),(19,19)]); line([(5,19),(19,5)])
    elif name == 'sound':
        line([(3,9),(8,9),(14,3),(14,21),(8,15),(3,15)],True); line([(18,7),(21,12),(18,17)])
    else:
        circle(12,12,8); line([(8,12),(11,15),(17,8)])


def backdrop(surface, variant=0):
    """A graphic visitor-guide backdrop until chapter illustrations are authored."""
    w,h=surface.get_size()
    for y in range(h):
        t=y/max(1,h-1)
        color=tuple(round(a+(b-a)*t) for a,b in zip((222,236,226),(244,245,232)))
        pygame.draw.line(surface,color,(0,y),(w,y))
    # Abstract park-guide geometry, intentionally not a map of playable locations.
    shade=(205,222,207)
    for x,y,r in [(980,230,170),(1150,530,210),(720,490,120)]:
        pygame.draw.circle(surface,shade,(x,y),r)
        pygame.draw.circle(surface,(225,236,220),(x,y),r-16)
    path=[(690,0),(690,270),(850,270),(850,620),(1280,620)]
    pygame.draw.lines(surface,(248,248,235),False,path,30)
    pygame.draw.lines(surface,(192,211,195),False,path,2)
    for x,y in [(690,180),(850,380),(1070,620)]:
        pygame.draw.circle(surface,GREEN,(x,y),7)
    pygame.draw.circle(surface,RED,(849,381),3)
