#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split, tie_compare
from peer import Peer

class SpudStd(Peer):

    def post_init(self):
        # print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.slots = 3
        self.unchoked = []


    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.
        

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        # random.shuffle(needed_pieces)

        # logging.debug("%s here: still need pieces %s" % (
          #  self.id, needed_pieces))

        #logging.debug("%s still here. Here are some peers:" % self.id)

        piece_counts = dict()

        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))
            logging.debug("peer info: %s" % (p))
            #### request rarest first functionality #####

            for piece in p.available_pieces:
                if piece in np_set:
                    if piece in piece_counts:
                        piece_counts[piece].append(p.id)
                    else:
                        piece_counts[piece] = [p.id]
                    ###### request rarest first functionality ####
        
        # logging.debug("number of pieces needed: %s" % (len(np_set)))
        # logging.debug("number of pieces available: %s" % (len(piece_counts)))

        # logging.debug("piece_counts: %s" % (piece_counts))
        rarest_pieces = sorted(piece_counts, key = piece_counts.get, cmp = tie_compare)
        # logging.debug("rarest_pieces: %s" % (rarest_pieces))
        # logging.debug("And look, I have my entire history available too:")
        # logging.debug("look at the AgentHistory class in history.py for details")
        # logging.debug(str(history))
 
        reqs_perpeer = {p.id:0 for p in peers}
        for piece_id in rarest_pieces:
        ### TODO check most recent round and see if you uploaded the most to ### 
            ## for now, randomly pick a peer to request ##
            cand_peers = filter(lambda x: reqs_perpeer[x] < self.max_requests, piece_counts[piece_id])
            if len(cand_peers) < 1:
                continue
            peer_id = random.choice(cand_peers)
            # if reqs_perpeer[peer_id] < self.max_requests:
            reqs_perpeer[peer_id] = reqs_perpeer[peer_id] +1
            # logging.debug("peer_id: %s, requests: %s, max: %s" % (peer_id, reqs_perpeer[peer_id], self.max_requests))
      
                
            start_block = self.pieces[piece_id]
            r = Request(self.id, peer_id, piece_id, start_block)
            requests.append(r)
        # logging.debug("number of requests made: %s" % (len(requests)))
        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """
        round = history.current_round()
        # logging.debug("%s again.  It's round %d." % (
            # self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            # logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            # logging.debug("Still here: uploading")

            ## get list of requesters
            requesters = set([req.requester_id for req in requests])

            peer_blocks = dict()
            ## look at the last history
            downloads = list(history.downloads[-1])
            if len(history.downloads) > 1:
                downloads.extend(history.downloads[-2])
            for d in downloads:
                ## sort, and take top 3 to unchoke
                ## if there aren't 3, then we only optimistically unchoke 1 person
                if d in requesters:
                    if d.from_id in peer_blocks:
                        peer_blocks[d.from_id] += d.blocks
                    else:
                        peer_blocks[d.from_id] = d.blocks
            ## sort requesters by highest # of blocks for the last round
            ## thee requesters are only peers that have uploaded to us recently
            sorted_requesters = sorted(peer_blocks, key = peer_blocks.get)[::-1]
            chosen = []

            # logging.debug("chosen, %s", chosen)
            if len(sorted_requesters) >= self.slots:
                # pick top 3
                chosen = sorted_requesters[:self.slots]
            else:  
                chosen = sorted_requesters

            # if there are not enough requesters that uploaded to us
            # unchoke s-1-len(chosen) more for this round
            if len(requesters) > len(chosen):
                for c in chosen:
                    requesters.remove(c)
                extra = random.sample(requesters, min(self.slots - len(chosen), len(requesters)))
                chosen.extend(extra)
            ## optimistic unchocking up to remaining number of slots
            ## if round is 0 mod 3
            if (round % 3 == 0):
                if len(requesters) > len(chosen):
                    for c in extra:
                        requesters.remove(c)
                    ## chosen append someone random
                    optimistic = random.choice(list(requesters))
                    chosen.append(optimistic)
                    self.unchoked = optimistic

            else:
                chosen.append(self.unchoked)
            # logging.debug("chosen: %s", chosen)
            # request = random.choice(requests)
            # Evenly "split" my upload bandwidth among the one chosen requester
            assert(len(chosen)>0)
            assert(len(chosen)<=4)

            bws = even_split(self.up_bw, len(chosen))
            # random.shuffle(bws)
        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
        # logging.debug("Uploads %s", len(uploads))
        return uploads
