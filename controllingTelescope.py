from motordrive import futDrive


def evalu_degree(current_ra, current_dec, ra, dec):
    """
    Beregner hvor meget teleskopet skal flyttes i RA og DEC
    ud fra den nuværende position og den ønskede position.
    """

    # Hvis RA-værdien er større end 180 grader,
    # justeres RA og DEC for at tage højde for
    # koordinatsystemets omdrejning
    if ra > 180:
        ra -= 180
        dec = 180 - dec

    # Beregner forskellen mellem ønsket og nuværende RA
    new_ra = ra - current_ra

    # Beregner forskellen mellem ønsket og nuværende DEC
    new_dec = dec - current_dec

    # Returnerer:
    # - hvor meget motorerne skal bevæge sig (new_ra, new_dec)
    # - den nye absolutte position (ra, dec)
    return new_ra, new_dec, ra, dec


def changing_pos_manual():
    """
    Giver mulighed for manuelt at indtaste ønsket RA og DEC.
    """

    try:
        # Beder brugeren indtaste ønsket RA og DEC
        ra = float(input("Type wanted ra: "))
        dec = float(input("Type wanted dec: "))

    except:
        # Fejl hvis input ikke kan konverteres til tal
        raise TypeError("Must type float or int value")

    # Returnerer de manuelt indtastede værdier
    return ra, dec

