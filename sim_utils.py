import numpy as np
import matplotlib.pyplot as plt
from run_limits import capture_conductor_pressure

N = 50
dt = 1
dx = 1
A = 0.031
V = A*dx
komp = 6.4e-6  # kg/(m3*Pa), ideal methane near 300 K
gas_covolume = 0.0027  # m3/kg
ro = 1200
Pu_delta = 10000
ro_heavy = 1400
atm = 101325.0
Cd = 0.001

# M= [M_drillmud, M_heavy_mud, M_gas, V_gas]

P = [0.0 for _ in range(N)]
Pn = [[0.0, 0.0, 0.0] for _ in range(N)]

def rog(p):
    pressure = max(float(p), 1.0)
    ideal_density = komp * pressure
    return ideal_density / (1 + gas_covolume * ideal_density)

def drilling_fluid(ro):
 def rol(p):
    return ro*(1 + 0)
 return rol




def P_Stutzer(q, pos,ro):
    return  ro*q**2/(pos*Cd)**2

def Q_Stutzer(P, pos, ro):
    if pos <= 0 or ro <= 0 or P <= 0:
        return 0.0
    return Cd * pos * (P / ro) ** 0.5

qconst = 0.001 #10 litres/sec
k = 0.001/ 10000 # at 0.1 ATM produces qconst  
Ppl = 500*ro*9.8 + 100000



def get_init(v_num, well_l, vpm, gaz_v, ro, pu, dpump_low):
    v_delta = well_l * vpm / v_num
   #v_total = well_l * vpm
    l_gaz = gaz_v / vpm
    if l_gaz > 0.9 * well_l:
        return -1
    l_liquid = well_l - l_gaz
    rol = ro
    gaz_p = rol*l_liquid*9.81 + pu
    M_init = [[0.0, 0.0, 0.0, 0.0] for _ in range(v_num)]
    idx= -1
    while True:
        gaz_in_cell = min(gaz_v, v_delta)
        gaz_v -=  v_delta
        m_gaz = rog(gaz_p) * gaz_in_cell
        m_liquid = ro * (v_delta - gaz_in_cell)
        M_init[idx] = [m_liquid, m_gaz, 0, gaz_in_cell]
        if gaz_v<=0:
            for row in M_init[0:idx]:
                row[0] = ro * v_delta
            break
        idx -= 1

    pzab = pu + l_liquid*9.81*rol + l_gaz*9.81*rog(gaz_p)
    ppl = (pu + l_liquid*9.81*rol + l_gaz*9.81*rog(pzab) + pzab) / 2
    sidpp = pzab - well_l*9.81*rol + dpump_low
    return M_init,ppl,sidpp

def stolb_state(M,Pu,ro,ro_heavy):
    Pverh = Pu
    for i in range(len(M)-1,-1,-1):
        #print(M[i][1])
        V[i] = M[i][0] / ro + M[i][1] / rog(Pverh) + M[i][2] / ro_heavy
       # print(V[i])
        total_m = M[i][0] + M[i][1] + M[i][2]
        P[i] = Pverh
        Pverh = Pverh + total_m * 9.81 / A
    return V, P

 


def s_solver(A, Pu_delta, iters, M, ro, ro_heavy, Pu, V_real,V_cs):
    P_cs = -1
    Pverh = Pu
    Pverh_n = Pu - Pu_delta
    Pverh_v = Pu + Pu_delta
    rol = ro
    rolh = ro_heavy
    for _ in range(iters):
        P_cs = -1
        Vn0,Vn1,Vn2 = 0,0,0
        for row in M:
            Vn0 += row[0] / rol + row[1] / rog(Pverh_n) + row[2] / rolh
            Vn1 += row[0] / rol + row[1] / rog(Pverh) + row[2] / rolh
            Vn2 += row[0] / rol + row[1] / rog(Pverh_v) + row[2] / rolh
            total_m = row[0] + row[1] + row[2]
            Pverh_n, Pverh, Pverh_v = Pverh_n + total_m * 9.81 / A, Pverh + total_m * 9.81 / A, Pverh_v + total_m * 9.81 / A
            P_cs = capture_conductor_pressure(P_cs, Vn1, V_cs, Pverh)
            #print(Vn1)
        if V_real>=Vn1:
            k =  - Pu_delta  / max((Vn0 - Vn1), 0.000000001)
            b =  Pu - k*Vn1
            Pu_real = k*V_real + b
        else:
            k = - Pu_delta / max((Vn1 - Vn2), 0.000000001)
            b =  Pu - k*Vn1
            Pu_real = k*V_real + b
        Pzab = Pverh    
        Pu =  Pu_real   
        Pverh = Pu
        Pu_delta = Pu_delta / 1.5
        Pverh_n = Pu - Pu_delta
        Pverh_v = Pu + Pu_delta
        
    return Pu_real, Pzab, Pzab - Pu_real, P_cs





def CP(P_low, P_zab, ro,ro_heavy, heavy_poz, well_l):
    return P_low + max(P_zab - ro_heavy*heavy_poz*9.81 - ro*(well_l-heavy_poz)*9.81, 0)

def Q_gaz(kprod, Ppl,Pzab):
    return  max(kprod*(Ppl-Pzab),0)
    
        

      
def stolb_up_updater(M,Pu,pos,dt, ro, ro_heavy):
    if not M:
        return M

    while True:
        V_verh = M[0][0] / ro + M[0][2] / ro_heavy + M[0][3]
        if V_verh <= 0:
            if not any(row[0] / ro + row[2] / ro_heavy + row[3] > 0 for row in M[1:]):
                return M
            M.pop(0)
            M.append([0,0,0,0])
            continue

        rosm = (M[0][0] + M[0][2] + M[0][1]) / V_verh
        Q = Q_Stutzer(Pu - 10**5, pos, rosm)
        if Q <= 0:
            return M
        V_out = Q*dt
        if V_out >= V_verh:
            dt = dt - dt*V_verh / V_out
            M.pop(0)
            M.append([0,0,0,0]) if M[-1] != [0,0,0,0] else True
        else:
            k = (V_verh - V_out) / V_verh
            M[0][0], M[0][2], M[0][1], = M[0][0] * k, M[0][2] * k, M[0][1] * k
            return M        


        
        
def stolb_down_updater(M,ro_heavy, ro, q_heavy, q_light, pzab, Pu, ppl, pos, k,dt):
    if not M:
        return M
    M0 = q_light*dt
    M2 = q_heavy*dt
    dp = k*max(( ppl - pzab),0)
    #print(dp)
    mixture_volume = M[0][0]/ro + M[0][2]/ro_heavy + M[0][1]/rog(Pu)
    if mixture_volume > 0:
        rosm = (M[0][0] + M[0][2] + M[0][1]) / mixture_volume
    else:
        rosm = rog(Pu)
    V1 = max(Q_Stutzer(dp, pos, rosm)*0.8,Q_Stutzer(dp, 0.1, rosm))* dt
    M[-1][0],M[-1][1],M[-1][2],M[-1][3] = M[-1][0] + M0, M[-1][1] + V1*rog(pzab), M[-1][2] +M2, M[-1][3] + V1
    
    
    return M
    

def get_init_dp(v_num, well_l, vpm_dp, ro, pzab):
    v_delta = well_l * vpm_dp / v_num
    M_init = [[ro * v_delta, 0.0, 0.0, 0.0] for _ in range(v_num)]
    sidpp = pzab - well_l*ro*9.81
    return M_init,sidpp


def dp_state_old(v_num, well_l, M_init, rol, roh, q_light, q_heavy):
    delta_v = well_l/v_num
    if M_init[0][0]/rol + M_init[0][2]/roh + q_light + q_heavy > delta_v:
        M_init.append([q_light*rol,0,q_heavy*roh,0])
        M_init[0][0] = M_init[0][0] + q_light*rol
        M_init[0][2] = M_init[0][2] + q_heavy*roh
    return light_v, heavy_v, heavy_poz





def dp_state(M, dt, q_light, q_heavy, ro, ro_heavy):
    if not M:
        return M, 0, 0

    light_out_v = 0
    heavy_out_v = 0
    M[-1][0] = M[-1][0] + q_light * dt * ro
    M[-1][2] = M[-1][2] + q_heavy * dt * ro_heavy
    Q = q_light + q_heavy
    if Q <= 0:
        return M, light_out_v, heavy_out_v
    while True:
        V_niz = M[0][0] / ro + M[0][2] / ro_heavy
        if V_niz <= 0:
            if not any(row[0] / ro + row[2] / ro_heavy > 0 for row in M[1:]):
                return M, light_out_v, heavy_out_v
            M.pop(0)
            #M.append([0,0,0,0])
            continue
        V_out = Q * dt
        if V_out > V_niz:
            dt = dt - dt * V_niz / V_out
            light_out_v += M[0][0] / ro
            heavy_out_v += M[0][2] / ro_heavy
            M.pop(0)
            M.append([0,0,0,0]) if M[-1] != [0,0,0,0] else True
        else:
            k = (V_niz - V_out) / V_niz
            M[0][0], M[0][2] = M[0][0] * k, M[0][2] * k
            light_out_v += M[0][0] * (1-k) / ro
            heavy_out_v += M[0][2] * (1-k) / ro_heavy
            return M, light_out_v, heavy_out_v




def m_reconstruct(M, rol, roh, pu_updated, A ):
    total_v = 0
    for row in M:
        vl = row[0]/rol
        vh = row[2]/roh
        vg = row[1]/rog(pu_updated)
        pu_updated = pu_updated + (row[0] + row[2] + row[1]) * 9.81 / A
        row[3] = vg
        
            


def svg_preconstruct(M,rol,roh):
    total_v = 0
    svg_data = []
    for row in M:
        light_volume = row[0] / rol
        heavy_volume = row[2] / roh
        gas_volume = max(row[3], 0.0)
        liquid_volume = light_volume + heavy_volume
        V_cell = liquid_volume + gas_volume
        total_v += V_cell
        liquid_tone = 1 if heavy_volume > light_volume else 0
        gas_fraction = gas_volume / V_cell if V_cell > 0 else 0.0
        svg_data.append([V_cell, liquid_tone, gas_fraction])

    if total_v > 0:
        for row in svg_data:
            row[0] = row[0] / total_v
    return svg_data


def dp_surf_press(M, lowp, Q, pzab, A, low_pump_rate):
    P_tot = pzab + lowp* Q**2/low_pump_rate**2
    for row in M:
        P_tot -= (row[0] + row[2]) * 9.81 / A
    return max(10000, P_tot)


def gas_migrate(M, rol, roh, cell_v, vpm, dt, speed_1, speed_2, suspension_param ): #cell_v = well_l * vpm / v_num

    for i in range(1,len(M)):
        if M[i][3] <= 0:
            continue

        upper_liquid_v = M[i-1][0] / rol + M[i-1][2] / roh
        if upper_liquid_v <= 0:
            continue
        
        should_i_stay_or_should_i_do = True
        beg = False
        
        if (M[i][0] + M[i][2] <0.01 and M[i][1]>0 ) or i == len(M)-1: 
            should_i_stay_or_should_i_do = True
        elif M[i+1][1] > 0 or ( M[i][1] == 0 ):
            should_i_stay_or_should_i_do = False
            
        if should_i_stay_or_should_i_do == True:
            if i == len(M)-1:
                beg = True
            alpha = max((M[i][3])/(M[i][0]/rol + M[i][2]/roh + M[i][3]),(M[i-1][3])/(M[i-1][0]/rol + M[i-1][2]/roh + M[i-1][3]))
            speed = speed_1 if alpha > suspension_param else speed_2
            V_to_pass_avail = min(speed * vpm * dt, M[i][3])
            V_to_transfer = min(V_to_pass_avail, upper_liquid_v)
            m_gas_up = M[i][1] * V_to_transfer / M[i][3]
            ml_down = M[i-1][0] * V_to_transfer / upper_liquid_v
            mh_down = M[i-1][2] * V_to_transfer / upper_liquid_v
            M[i][3] -= V_to_transfer
            M[i-1][3] += V_to_transfer

            M[i][0] += ml_down
            M[i][2] += mh_down
            M[i-1][1] += m_gas_up 
            M[i-1][0] -= ml_down
            M[i-1][2] -= mh_down
            M[i][1] -= m_gas_up 
            ##

            
            
            
            
        
