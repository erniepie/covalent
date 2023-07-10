/**
 * Copyright 2023 Agnostiq Inc.
 *
 * This file is part of Covalent.
 *
 * Licensed under the GNU Affero General Public License 3.0 (the "License").
 * A copy of the License may be obtained with this software package or at
 *
 *      https://www.gnu.org/licenses/agpl-3.0.en.html
 *
 * Use of this file is prohibited except in compliance with the License. Any
 * modifications or derivative works of this file must retain this copyright
 * notice, and modified files must contain a notice indicating that they have
 * been altered from the originals.
 *
 * Covalent is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
 *
 * Relief from the License may be granted by purchasing a commercial license.
 */

import { Grid, Typography, SvgIcon, Box, Modal, Paper, Skeleton } from '@mui/material'
import React, { useState } from 'react'
import theme from '../../utils/theme'
import { ReactComponent as CircuitLarge } from '../../assets/qelectron/circuit-large.svg'
import { ReactComponent as CloseSvg } from '../../assets/close.svg'
import SyntaxHighlighter from '../common/SyntaxHighlighter'
import { useSelector } from 'react-redux';

const styles = {
  outline: 'none',
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  p: 4,
  width: ' 95%',
  height: '95%',
  bgcolor: '#0B0B11E5',
  border: '2px solid transparent',
  boxShadow: 24,
}

const SingleGrid = ({ title, value }) => {

  const qelectronJobOverviewIsFetching = useSelector(
    (state) => state.electronResults.qelectronJobOverviewList.isFetching
  );

  return (
    <Grid>
      <Typography
        sx={{
          fontSize: theme.typography.sidebarh3,
          color: (theme) => theme.palette.text.tertiary,
        }}
      >
        {title}
      </Typography>
      {qelectronJobOverviewIsFetching && !value ?
        <Skeleton data-testid="node__box_skl" width={30} /> : <>
          <Typography
            sx={{
              fontSize: theme.typography.sidebarh2,
              color: (theme) => theme.palette.text.primary,
            }}
          >
            {value ? value : '-'}
          </Typography>
        </>}
    </Grid>
  )
}

const Circuit = ({ circuitDetails }) => {
  const [openModal, setOpenModal] = useState(false)

  const handleClose = () => {
    setOpenModal(false)
  }
  const qelectronJobOverviewIsFetching = useSelector(
    (state) => state.electronResults.qelectronJobOverviewList.isFetching
  );

  return (
    <Grid
      px={4}
      pt={2}
      container
      flexDirection="column
    "
    >
      <Grid
        id="topGrid"
        item
        container
        xs={11.85}
        justifyContent="space-between"
      >
        <SingleGrid title="No. of Qbits" value={circuitDetails?.total_qbits} />
        <SingleGrid title="No.1 Qbit Gates" value={circuitDetails?.qbit1_gates} />
        <SingleGrid title="No.2 Qbit Gates" value={circuitDetails?.qbit2_gates} />
        <SingleGrid title="Depth" value={circuitDetails?.depth} />
      </Grid>
      <Grid id="bottomGrid" mt={3}>
        <Typography
          sx={{
            fontSize: theme.typography.sidebarh3,
            color: (theme) => theme.palette.text.tertiary,
          }}
        >
          Circuit
        </Typography>

        <Grid sx={{ width: '80%', height: '100%' }}>
          <Paper
            elevation={0}
            sx={(theme) => ({
              bgcolor: theme.palette.background.outRunBg,
            })}
          >
            {' '}
            <SyntaxHighlighter src={circuitDetails?.circuit_diagram} preview fullwidth isFetching={qelectronJobOverviewIsFetching} />
          </Paper>
        </Grid>
      </Grid>
      <Modal
        open={openModal}
        onClose={handleClose}
        aria-labelledby="modal-modal-title"
        aria-describedby="modal-modal-description"
      >
        <Box sx={styles}>
          <Grid container sx={{ height: '100%' }}>
            <Grid item xs={11} sx={{ height: '100%' }}>
              <Grid
                mt={2}
                container
                justifyContent="center"
                sx={{ width: '900px', height: '320px' }}
              >
                <span
                  style={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    justifyContent: 'flex-end',
                  }}
                >
                  <SvgIcon
                    aria-label="view"
                    sx={{
                      width: '100%',
                      height: '100%',
                      color: (theme) => theme.palette.text.primary,
                    }}
                    component={CircuitLarge}
                    viewBox="0 0 900 320" // Specify the viewBox to match the desired container size
                  />
                </span>
              </Grid>
            </Grid>
            <Grid
              item
              pr={1}
              pt={0.5}
              xs={1}
              sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                cursor: 'pointer',
              }}
            >
              <span style={{ flex: 'none' }} onClick={handleClose}>
                <SvgIcon
                  aria-label="view"
                  sx={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    mr: 0,
                    mt: 1,
                    pr: 0,
                  }}
                >
                  <CloseSvg />
                </SvgIcon>
              </span>
            </Grid>
          </Grid>
        </Box>
      </Modal>
    </Grid>
  )
}

export default Circuit