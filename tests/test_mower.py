from landroidcc import LandroidStatus


def test_status_update_successful():
    # ARRANGE
    input = '{"cfg":{"id":1,"lg":"it","tm":"08:57:38","dt":"28/04/2019",' \
            '"sc":{"m":1,"p":0,"d":[["00:00",0,0],["10:00",120,0],["10:00",120,0],["10:00",120,0],["10:00",120,1],' \
            '["10:00",120,0],["10:00",120,0]]},' \
            '"cmd":0,"mz":[0,0,0,0],"mzv":[0,0,0,0,0,0,0,0,0,0],"rd":60,"sn":"1234567890123456789h"},' \
            '"dat":{"mac":"123456789012","fw":2.74,"bt":{"t":6.9,"v":19.79,"p":100,"nr":4,"c":0},' \
            '"dmp":[1.0,-0.4,280.2],"st":{"b":420,"d":6877,"wt":455},"ls":1,"le":5,"lz":0,"rsi":-71,' \
            '"lk":0,"act":1,"conn":"wifi"}}'

    # ACT
    status = LandroidStatus(input)

    # ASSERT
    assert status