def target(shard):
    if shard == 0:
        return dict(old_job=150049, old_target='150039_0', client_job=150946,
                    host_job=150933,node='aias-compute-01',seeds=[2030,2032],port=18049)
    if shard == 1:
        return dict(old_job=150775,old_target='150775',client_job=150775,
                    host_job=None,node='aias-compute-2',seeds=[2031,2033],port=18775)
    raise ValueError('Only the two explicitly authorized washout services may migrate')

def ordered_devices(actual,expected,visible):
    tokens=visible.split(',')
    if len(actual)!=len(expected) or len(tokens)!=len(actual) or set(actual)!=set(expected):
        raise ValueError('Allocated GPU identities differ; refuse inference and result writes')
    return ','.join(tokens[actual.index(uuid)] for uuid in expected)

def verify_prefix(old,new):
    if not new.startswith(old):raise ValueError('Completed result prefix changed')
